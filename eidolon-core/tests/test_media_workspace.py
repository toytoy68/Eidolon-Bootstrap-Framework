# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_workspace.py
# Description : Initialisation média cohérente et coupures sans reprise
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.conversation_store import ConversationStore
from eidolon_core.media_agents import MediaError
from eidolon_core.media_cli import main
from eidolon_core.media_workspace import initialize, inspect
from eidolon_core.store import Store


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.conv = ConversationStore(Store(self.state), create=True)
        self.workspace = self.root / 'media'

    def test_init_coherent_private_offline_and_state_unchanged(self):
        before = {str(p): p.read_bytes() for p in self.state.rglob('*') if p.is_file()}
        with patch('socket.socket.connect', side_effect=AssertionError('network')):
            result = initialize(self.workspace, state=self.state)
            view = inspect(self.workspace, workspace_id=result['workspace_id'])
        self.assertEqual(view['state'], 'LOCAL_WORKSPACE_READY')
        self.assertEqual(view['configuration_state'], 'INCOMPLETE')
        self.assertEqual(view['resource_state'], 'AVAILABLE')
        self.assertEqual(result['store_id'], self.conv.store_id)
        self.assertFalse(result['authorizes_execution'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.state.rglob('*') if p.is_file()})
        for p in [self.workspace, *self.workspace.rglob('*')]:
            self.assertEqual(p.stat().st_mode & 0o777, 0o700 if p.is_dir() else 0o600)
        self.assertNotIn(str(self.root), json.dumps(view))

    def test_existing_root_never_overwritten(self):
        result = initialize(self.workspace, state=self.state)
        before = (self.workspace / 'workspace.json').read_bytes()
        with self.assertRaises(FileExistsError): initialize(self.workspace, state=self.state)
        self.assertEqual(before, (self.workspace / 'workspace.json').read_bytes())
        with self.assertRaisesRegex(MediaError, 'IDENTITY_MISMATCH'):
            inspect(self.workspace, workspace_id='mws-' + '0' * 32)

    def test_missing_core_does_not_create_workspace(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            code = main(['workspace-init', '--root', str(self.workspace), '--state', str(self.root / 'absent')])
        self.assertEqual(code, 2)
        self.assertFalse(self.workspace.exists())
        self.assertNotIn(str(self.root), output.getvalue())

    def test_each_interruption_retained_and_requires_review(self):
        for stage in ('intent', 'artifacts', 'resources', 'worker', 'configuration'):
            target = self.root / stage
            def stop(current):
                if current == stage: raise RuntimeError('synthetic crash')
            with self.assertRaisesRegex(RuntimeError, 'synthetic crash'):
                initialize(target, state=self.state, checkpoint=stop)
            record = json.loads((target / 'workspace.json').read_bytes())
            self.assertEqual(inspect(target, workspace_id=record['workspace_id'])['state'], 'REVIEW_REQUIRED')
            with self.assertRaises(FileExistsError): initialize(target, state=self.state)

    def test_config_mismatch_and_component_replacement_detected(self):
        result = initialize(self.workspace, state=self.state)
        config_file = self.workspace / 'media.json'
        config = json.loads(config_file.read_bytes()); config['artifact_store']['root'] = '/elsewhere'
        config_file.write_text(json.dumps(config))
        view = inspect(self.workspace, workspace_id=result['workspace_id'])
        self.assertEqual(view['state'], 'REVIEW_REQUIRED')
        self.assertEqual(view['configuration_state'], 'WORKSPACE_CONFIG_MISMATCH')
        (self.workspace / 'worker').rename(self.workspace / 'old-worker')
        (self.workspace / 'worker').symlink_to(self.workspace / 'old-worker', target_is_directory=True)
        self.assertEqual(inspect(self.workspace, workspace_id=result['workspace_id'])['components']['worker'], 'UNAVAILABLE_OR_CHANGED')

    def test_cli_human_review_exit_and_malformed_manifest(self):
        result = initialize(self.workspace, state=self.state)
        args = ['workspace-inspect', '--root', str(self.workspace), '--workspace-id', result['workspace_id'], '--format', 'human']
        output = io.StringIO()
        with contextlib.redirect_stdout(output): self.assertEqual(main(args), 0)
        self.assertIn('Eidolon Core Technologies (ECT)', output.getvalue())
        self.assertNotIn('[OK]', output.getvalue())
        (self.workspace / 'media.json').unlink()
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(main(args), 2)
        manifest = self.workspace / 'workspace.json'
        value = json.loads(manifest.read_bytes()); value['state'] = []
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(MediaError, 'INVALID_MEDIA_WORKSPACE'):
            inspect(self.workspace, workspace_id=result['workspace_id'])
