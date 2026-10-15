# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_maintenance_resume_g264.py
# Description : Reprise du contrôleur de maintenance après interruption, état durable réel (Claude, G264-8)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit integration, like G254: EIDOLON_MEMORY_INTEGRATION=1 with Memory on PYTHONPATH, qdrant_client
in-memory. Every "restart" builds a NEW controller from the SAME sqlite files: the only state carried
over is the durable one. Every call goes through run_maintenance_tick with an explicit host observation;
nothing loops, nothing retries by itself, no sensor is faked beyond the synthetic observation."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os

import pytest

from eidolon_core.maintenance_runner import run_maintenance_tick

pytestmark = pytest.mark.skipif(os.environ.get("EIDOLON_MEMORY_INTEGRATION") != "1",
                                reason="explicit Memory integration (EIDOLON_MEMORY_INTEGRATION=1)")

from zoneinfo import ZoneInfo
# 05:00 Europe/Paris tomorrow: inside the default 04:00-08:00 window, with room for every scenario below.
NIGHT = (datetime.now(ZoneInfo("Europe/Paris")) + timedelta(days=1)).replace(
    hour=5, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def observation(at, *, idle_minutes=60, boot_minutes=120, load=0.1):
    value = dict(source="host.proc", at=at.isoformat(),
                 last_activity=(at - timedelta(minutes=idle_minutes)).isoformat(),
                 boot_at=(at - timedelta(minutes=boot_minutes)).isoformat())
    if load is not None:
        value["load"] = dict(observed_at=(at - timedelta(seconds=10)).isoformat(), ratio=load, limit=0.7)
    return value


class World:
    def __init__(self, tmp_path, client):
        from core.backend.filesystem import FilesystemBackend
        from core.backend.models import Memory
        from core.indexing.change_journal import ChangeJournal
        from core.indexing.qdrant_index import QdrantIndex
        from core.indexing.worker_canonical import CanonicalReader
        self.tmp, self.root = tmp_path, tmp_path / "persistent"
        FilesystemBackend(self.root, tmp_path / "history").store(Memory("a", content="synthetic"))
        _, digest = CanonicalReader(self.root)("a")
        self.journal = ChangeJournal(tmp_path / "changes.sqlite3")
        self.seq = self.journal.begin("a", 1, "UPSERT", digest)
        self.journal.published(self.seq)
        self.index = QdrantIndex(client, "eidolon_g264_resume", embed=lambda _: [1., 0.], dimensions=2,
                                 embedding_id="synthetic-v1", create=True)
        self.factories = 0

    def factory(self):
        """A fresh controller each time: in-memory state of the previous one is gone ("restart")."""
        from core.indexing.maintenance import IndexMaintenance
        self.factories += 1
        return IndexMaintenance(self.tmp / "cycle.sqlite3", self.journal,
                                canonical_checkpoint=self.tmp / "canonical.sqlite3",
                                orphan_checkpoint=self.tmp / "orphans.sqlite3", canonical_root=self.root,
                                index=self.index, authorize=lambda *_: True, profile_id="owner",
                                expected_profile_id="owner", expected_model_id="synthetic-v1")

    def tick(self, at, **obs):
        return run_maintenance_tick(observation(at, **obs), now=at + timedelta(seconds=5), expected_source="host.proc",
                                    max_observation_age=timedelta(minutes=2), max_load_age=timedelta(minutes=2),
                                    make_maintenance=self.factory)


@pytest.fixture
def world(tmp_path):
    qdrant = pytest.importorskip("qdrant_client")
    with closing(qdrant.QdrantClient(":memory:")) as client:
        yield World(tmp_path, client)


def indexed(world):
    return world.index.status().documents == 1 and world.journal.intent(world.seq).state == "INDEXED"


def test_stop_between_selection_and_indexing_resumes_from_durable_state(world):
    first = world.tick(NIGHT)
    assert first.report.state == "ACTIVE" and first.report.detail["pass_started"] == world.seq
    assert not indexed(world)                                     # selection recorded, nothing indexed yet
    # Process stops here. A new controller, minutes later, resumes the same pass from sqlite.
    second = world.tick(NIGHT + timedelta(minutes=3))
    assert indexed(world) and world.factories == 2                # one factory per explicit host call


def test_restart_with_a_recent_boot_or_recent_activity_defers_then_resumes(world):
    assert world.tick(NIGHT).report.state == "ACTIVE"
    rebooted = NIGHT + timedelta(minutes=5)
    report = world.tick(rebooted, boot_minutes=2).report           # the machine just restarted
    assert report.state == "DEFERRED" and "BOOT_RECENT" in report.detail["reasons"] and not indexed(world)
    report = world.tick(rebooted + timedelta(minutes=10), boot_minutes=12, idle_minutes=1).report
    assert report.state == "DEFERRED" and "ACTIVITY_RECENT" in report.detail["reasons"]
    later = rebooted + timedelta(minutes=45)                      # 30 min of inactivity, boot 45 min ago
    world.tick(later, boot_minutes=45, idle_minutes=31)
    assert indexed(world)


def test_unknown_load_after_restart_never_indexes_and_never_loops(world):
    assert world.tick(NIGHT).report.state == "ACTIVE"
    for minutes in (3, 6, 9):
        report = world.tick(NIGHT + timedelta(minutes=minutes), load=None).report
        assert report.state == "DEFERRED" and "LOAD_NOT_READY" in report.detail["reasons"]
    assert not indexed(world) and world.factories == 4             # exactly one controller per call
    world.tick(NIGHT + timedelta(minutes=12))
    assert indexed(world)


def test_a_crash_while_indexing_is_not_retried_in_the_same_call_and_a_later_call_completes_once(world, monkeypatch):
    assert world.tick(NIGHT).report.state == "ACTIVE"
    real = type(world.index).upsert_verified
    crashes = []

    def crash_once(self, *args, **kwargs):
        if not crashes:
            crashes.append(1)
            raise OSError("synthetic crash during indexing")
        return real(self, *args, **kwargs)
    monkeypatch.setattr(type(world.index), "upsert_verified", crash_once)
    report = world.tick(NIGHT + timedelta(minutes=3)).report       # the worker absorbs it per intent
    assert crashes == [1] and world.factories == 2 and not indexed(world)
    assert report.state != "COMPLETE"                              # never reported as done
    for minutes in (6, 9, 12):
        world.tick(NIGHT + timedelta(minutes=minutes))
        if indexed(world):
            break
    assert indexed(world) and world.index.status().documents == 1   # once, no duplicate point


def test_a_clock_moved_back_after_restart_requires_review(world):
    assert world.tick(NIGHT).report.state == "ACTIVE"
    report = world.tick(NIGHT - timedelta(minutes=10)).report       # restarted host with a wrong clock
    assert report.state == "CLOCK_REVERSED" and report.detail["review_required"] is True
    assert world.tick(NIGHT + timedelta(minutes=20)).report.state == "CLOCK_REVERSED"   # stays until review
    assert not indexed(world)
