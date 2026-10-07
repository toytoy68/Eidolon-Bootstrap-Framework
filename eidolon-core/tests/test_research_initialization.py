# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_initialization.py
# Description : Garde et pauses jamais recréées après une initialisation perdue
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_runtime import ResearchRuntime, SyntheticResearchBackend
from eidolon_core.store import Store


class Interrupted(BaseException):
    pass


def interrupt():
    raise Interrupted()


class ResearchInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.runtime = ResearchRuntime(self.store)
        self.fixture = self.store.directory / 'research-fixture'

    def binding(self):
        with sqlite3.connect(self.store.path) as db:
            return db.execute("SELECT value FROM sync_metadata WHERE key='research_fixture_guard_id'").fetchone()

    def unbind(self):
        with sqlite3.connect(self.store.path) as db:
            db.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")

    def files(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_first_use_pins_identity_and_existing_runtime_reopens_same_backend(self):
        first = self.runtime.configuration()
        self.assertEqual(self.binding(), (self.runtime.backend.guard_id,))
        before = self.files()
        second = ResearchRuntime(self.store)
        self.assertEqual(second.configuration(), first)
        self.assertEqual(self.files(), before)

    def test_guard_database_and_lock_missing_are_not_recreated(self):
        for filename in ('research-runs.sqlite3', 'research-runs.lock'):
            path = self.fixture / 'guard' / filename
            saved = path.read_bytes(); path.unlink()
            before = self.files()
            with self.subTest(file=filename), self.assertRaises(ContractError):
                ResearchRuntime(self.store)
            self.assertFalse(path.exists())
            self.assertEqual(self.files(), before)
            path.write_bytes(saved); path.chmod(0o600)

    def test_pause_file_missing_is_not_recreated(self):
        path = self.fixture / 'pauses.sqlite3'; path.unlink()
        before = self.files()
        with self.assertRaisesRegex(ContractError, 'RESEARCH_PAUSES_MISSING'):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_whole_fixture_missing_refused_even_before_first_mission(self):
        shutil.rmtree(self.fixture)
        before = self.files()
        with self.assertRaisesRegex(ContractError, 'RESEARCH_PAUSES_MISSING'):
            ResearchRuntime(self.store)
        self.assertFalse(self.fixture.exists())
        self.assertEqual(self.files(), before)

    def test_uncertain_intent_survives_missing_directory_and_restoration(self):
        guard = ResearchGuard(self.fixture / 'guard', create=False)
        cleaned = clean_query('synthetic interrupted')
        with self.assertRaises(Interrupted):
            guard.execute(interrupt, descriptor={'query_sha256': cleaned.cleaned_sha256,
                          'policy_id': 'synthetic', 'providers': ['synthetic']}, cleaned_query=cleaned)
        backup = self.root / 'backup'; shutil.move(self.fixture, backup)
        with self.assertRaises(ContractError):
            ResearchRuntime(self.store)
        self.assertFalse(self.fixture.exists())
        shutil.move(backup, self.fixture)
        reopened = ResearchRuntime(self.store)
        self.assertEqual(reopened.backend.guard_id, guard.guard_id)
        self.assertEqual(ResearchGuard(self.fixture / 'guard', create=False).inspect()['runs'][0]['state'], 'INTENT')
        with self.assertRaisesRegex(ContractError, 'WEB_RESEARCH_UNCERTAIN'):
            reopened.backend.execute({'query': 'new synthetic', 'required_pages': 1, 'operation_id': 'm-' + 'c' * 32}, {})

    def test_replacement_guard_with_new_identity_is_refused(self):
        shutil.rmtree(self.fixture / 'guard')
        ResearchGuard(self.fixture / 'guard', retain_queries=True)
        before = self.files()
        with self.assertRaisesRegex(ContractError, 'RESEARCH_BACKEND_CHANGED'):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_legacy_mission_adopts_only_matching_guard_without_configuration_change(self):
        mission = self.runtime.create_research('legacy query')
        self.unbind()
        reopened = ResearchRuntime(self.store)
        self.assertEqual(reopened.configuration(), mission['configuration'])
        self.assertEqual(self.binding(), (self.runtime.backend.guard_id,))
        self.assertEqual(self.store.get(mission['id']), mission)

    def test_legacy_mission_and_missing_fixture_do_not_authorize_first_use(self):
        self.runtime.create_research('legacy query')
        self.unbind(); shutil.rmtree(self.fixture)
        before = self.files()
        with self.assertRaises(ContractError):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)
        self.assertIsNone(self.binding())

    def test_legacy_mission_does_not_adopt_replacement_guard(self):
        self.runtime.create_research('legacy query')
        self.unbind(); shutil.rmtree(self.fixture / 'guard')
        ResearchGuard(self.fixture / 'guard', retain_queries=True)
        with self.assertRaisesRegex(ContractError, 'RESEARCH_BACKEND_CHANGED'):
            ResearchRuntime(self.store)
        self.assertIsNone(self.binding())

    def test_bad_binding_is_refused_without_repair(self):
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE sync_metadata SET value='PRIVATE_CANARY' WHERE key='research_fixture_guard_id'")
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^INVALID_RESEARCH_BACKEND_BINDING$'):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_partial_initialization_is_not_silently_completed(self):
        other = Store(self.root / 'other')
        with patch('eidolon_core.research_runtime.ResearchPauses', side_effect=Interrupted), self.assertRaises(Interrupted):
            ResearchRuntime(other)
        path = other.directory / 'research-fixture'
        self.assertTrue((path / 'guard/research-runs.sqlite3').exists())
        with self.assertRaisesRegex(ContractError, 'RESEARCH_PAUSES_MISSING'):
            ResearchRuntime(other)
        self.assertFalse((path / 'pauses.sqlite3').exists())

    def test_two_concurrent_initializers_share_one_identity(self):
        other = Store(self.root / 'parallel')
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda _: ResearchRuntime(other).backend.guard_id, range(2)))
        self.assertEqual(values[0], values[1])
        self.assertEqual(ResearchRuntime(other).backend.guard_id, values[0])

    def test_existing_empty_or_incomplete_pause_database_is_not_repaired(self):
        path = self.fixture / 'pauses.sqlite3'
        saved = path.read_bytes()
        for mode in ('empty', 'table_missing'):
            path.write_bytes(saved)
            if mode == 'empty':
                path.write_bytes(b'')
            else:
                with sqlite3.connect(path) as db:
                    db.execute('DROP TABLE pause_events')
            before = self.files()
            with self.subTest(mode=mode), self.assertRaisesRegex(ContractError, 'UNSUPPORTED_PAUSE_DATABASE'):
                ResearchRuntime(self.store)
            self.assertEqual(self.files(), before)

    def test_executor_does_not_repair_pause_schema_after_runtime_construction(self):
        path = self.fixture / 'pauses.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('DROP TABLE pause_events')
        before = self.files()
        with self.assertRaisesRegex(ContractError, 'UNSUPPORTED_PAUSE_DATABASE'):
            self.runtime.backend.execute({'query': 'synthetic', 'required_pages': 1, 'operation_id': 'm-' + 'd' * 32}, {})
        self.assertEqual(self.files(), before)

    def test_direct_backend_also_does_not_recreate_existing_folder(self):
        (self.fixture / 'guard/research-runs.sqlite3').unlink()
        with self.assertRaises(ContractError):
            SyntheticResearchBackend(self.fixture)
        self.assertFalse((self.fixture / 'guard/research-runs.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
