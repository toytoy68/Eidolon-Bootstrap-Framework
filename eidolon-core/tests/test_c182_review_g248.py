# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_c182_review_g248.py
# Description : Independent acceptance probes for Claude C182 host preparation.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import builtins
from pathlib import Path

import pytest

from tests.test_claude_offline_preflight import pre, repo
from tests.test_maintenance_observations import raw
from eidolon_core.maintenance_observations import normalize_host_observation


def secret(tmp_path, content='s' * 40):
    private = tmp_path / 'real' / 'private'
    private.mkdir(parents=True, mode=0o700)
    token = private / 'token'
    token.write_text(content)
    token.chmod(0o600)
    return token


def test_preflight_cannot_pass_a_link_in_any_credential_ancestor(tmp_path):
    token = secret(tmp_path)
    link = tmp_path / 'linked'
    link.symlink_to(token.parent.parent, target_is_directory=True)
    report = pre.check_credential(link / 'private' / 'token')
    assert report['result'] == 'FAIL'
    assert str(tmp_path) not in report['detail']


def test_preflight_cannot_pass_a_parent_traversal_rejected_by_the_reader(tmp_path):
    token = secret(tmp_path)
    assert pre.check_credential(token.parent / '..' / 'private' / 'token')['result'] == 'FAIL'


@pytest.mark.parametrize('length', [1, 31])
def test_impossibly_short_credential_fails_without_reading_it(tmp_path, length, monkeypatch):
    token = secret(tmp_path, 's' * length)
    def forbidden(*args, **kwargs):
        raise AssertionError('credential content must never be opened by preflight')
    monkeypatch.setattr(builtins, 'open', forbidden)
    assert pre.check_credential(token)['result'] == 'FAIL'


def test_untracked_source_is_not_a_clean_checkout(tmp_path):
    path = tmp_path / 'repo'
    head = repo(path)
    (path / 'untracked.py').write_text('not part of the expected commit')
    assert pre.check_checkout('core', path, head)['result'] == 'FAIL'


@pytest.mark.parametrize('minimum', [-1, 0, True, 1.5])
def test_invalid_disk_policy_cannot_pass(tmp_path, minimum):
    assert pre.check_disk(tmp_path, minimum)['result'] == 'FAIL'


def test_normalized_observation_keeps_its_provenance():
    observation = normalize_host_observation(raw())
    assert observation.source == 'host.proc'
    assert 'source' not in observation.tick_kwargs()  # Tick's existing API stays unchanged.


def test_host_observations_gate_the_actual_memory_cycle(tmp_path):
    import os
    if os.environ.get('EIDOLON_MEMORY_INTEGRATION') != '1':
        pytest.skip('explicit Memory integration')
    from contextlib import closing
    pytest.importorskip('qdrant_client')
    from qdrant_client import QdrantClient
    from core.backend.filesystem import FilesystemBackend
    from core.indexing.change_journal import ChangeJournal
    from core.indexing.maintenance import IndexMaintenance
    from core.indexing.qdrant_index import QdrantIndex
    canonical = tmp_path / 'persistent'
    FilesystemBackend(canonical, tmp_path / 'history')
    journal = ChangeJournal(tmp_path / 'changes.sqlite3')
    with closing(QdrantClient(':memory:')) as client:
        index = QdrantIndex(client, 'eidolon_g248_test', embed=lambda _: [1., 0.],
                            dimensions=2, embedding_id='synthetic-v1', create=True)
        cycle = IndexMaintenance(tmp_path / 'cycle.sqlite3', journal, canonical_root=canonical,
            canonical_checkpoint=tmp_path / 'canonical.sqlite3', orphan_checkpoint=tmp_path / 'orphans.sqlite3',
            index=index, authorize=lambda *args: True, profile_id='owner', expected_profile_id='owner',
            expected_model_id='synthetic-v1')
        unknown = normalize_host_observation({'source': 'host.proc', 'at': raw()['at']})
        deferred = cycle.tick(**unknown.tick_kwargs())
        assert deferred.state == 'DEFERRED'
        assert {'ACTIVITY_RECENT', 'BOOT_RECENT', 'LOAD_NOT_READY'} <= set(deferred.detail['reasons'])
        assert cycle.tick(**normalize_host_observation(raw()).tick_kwargs()).state == 'ACTIVE'
        assert journal.pending() == () and index.status().documents == 0
