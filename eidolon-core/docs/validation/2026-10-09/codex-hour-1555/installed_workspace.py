# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed_workspace.py
# Description : Recette CLI depuis le paquet installé, espace local uniquement
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import eidolon_core
from eidolon_core.store import Store
from eidolon_core.conversation_store import ConversationStore

assert 'site-packages' in eidolon_core.__file__
cli = str(Path(sys.executable).parent / 'eidolon-media')
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    conv = ConversationStore(Store(root / 'state'), create=True)
    def call(*args, code=0):
        result = subprocess.run([cli, *map(str, args)], capture_output=True, text=True)
        assert result.returncode == code, (result.returncode, result.stderr)
        return json.loads(result.stdout if code == 0 else result.stderr)
    created = call('workspace-init', '--root', root / 'media', '--state', root / 'state')
    observed = call('workspace-inspect', '--root', root / 'media', '--workspace-id', created['workspace_id'])
    assert observed['state'] == 'LOCAL_WORKSPACE_READY'
    assert observed['configuration_state'] == 'INCOMPLETE'
    assert observed['store_id'] == conv.store_id
    repeat = call('workspace-init', '--root', root / 'media', '--state', root / 'state', code=2)
    assert repeat['automatic_retry'] is False
    interruptions = []
    for stage in ('intent', 'artifacts', 'resources', 'worker', 'configuration'):
        target = root / stage
        child = subprocess.run([sys.executable, '-c',
            "import os,sys; from eidolon_core.media_workspace import initialize; "
            "initialize(sys.argv[1], state=sys.argv[2], checkpoint=lambda stage: "
            "os._exit(77) if stage == sys.argv[3] else None)", str(target), str(root / 'state'), stage],
            capture_output=True, text=True)
        assert child.returncode == 77, child.stderr
        marker = json.loads((target / 'workspace.json').read_bytes())
        observation = subprocess.run([cli, 'workspace-inspect', '--root', str(target),
            '--workspace-id', marker['workspace_id']], capture_output=True, text=True)
        assert observation.returncode == 2, observation.stderr
        assert json.loads(observation.stdout)['state'] == 'REVIEW_REQUIRED'
        call('workspace-init', '--root', target, '--state', root / 'state', code=2)
        interruptions.append(stage)
    print(json.dumps({'passed': True, 'process_exit_77_interruption_points': interruptions, 'installed_package': eidolon_core.__file__,
                      'cli_initialization': True, 'inspection': observed['state'],
                      'configuration': observed['configuration_state'], 'overwrite_refused': True,
                      'engines_installed_or_started': False, 'hardware_qualified': False}, indent=2))
