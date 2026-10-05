# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_probes.py
# Description : Reproductions synthétiques avant intégration des lots Claude
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
import os
from pathlib import Path
import tempfile

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import OllamaConfig, OllamaModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.targets import Catalog
from eidolon_core.tools import Registry, default_registry


def effect_then_error(parameters, context):
    with Path(os.environ['EIDOLON_PROBE_EFFECT']).open('a') as f:
        f.write('synthetic effect\n')
    raise ConnectionResetError('synthetic failure after effect')


def main():
    options = {'temperature': 0}
    model = OllamaModel(OllamaConfig(endpoint='http://127.0.0.1:1', model='synthetic', options=options))
    original = model.model_id
    options['temperature'] = 1
    print('caller options changed adapter:', model.config.options['temperature'] == 1)
    print('model_id unchanged after options mutation:', model.model_id == original)
    catalog = Catalog.from_config({'schema': 'targets/1', 'targets': [
        {'id': 'synthetic', 'name': 'Synthetic', 'kind': 'lan_service', 'capabilities': [
            {'name': 'files.read', 'effect': 'local_read', 'scope': {'roots': ['safe']}}]}]})
    before = catalog.fingerprint()
    catalog.manifest()['targets'][0]['capabilities'][0]['scope']['roots'].append('outside')
    print('returned manifest changed catalog:', before != catalog.fingerprint())
    with tempfile.TemporaryDirectory() as directory:
        effects = Path(directory) / 'effects'
        os.environ['EIDOLON_PROBE_EFFECT'] = str(effects)
        tool = replace(default_registry().get('text.stats'), execute=effect_then_error)
        runtime = Runtime(Store(Path(directory) / 'state'), registry=Registry([tool]))
        identity = runtime.create(DEMO_REQUEST)['id']
        print('first run:', runtime.run(identity)['status'])
        try:
            runtime.reconcile(identity, decision='no-effect', actor='probe', reason='error received')
            print('no-effect without confirmation: ACCEPTED')
            runtime.run(identity)
        except (ValueError, RuntimeError) as exc:
            print('no-effect without confirmation: REFUSED', str(exc))
        print('effects:', len(effects.read_text().splitlines()))


if __name__ == '__main__':
    main()
