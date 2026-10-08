# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : reproduce-g064-3.py
# Description : Reproduction synthétique du remplacement des pauses G064-3
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import tempfile
from eidolon_core.store import Store
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.research_pauses import ResearchPauses


def main():
    with tempfile.TemporaryDirectory(prefix='core-g064-3-') as temporary:
        root = Path(temporary)
        runtime = ResearchRuntime(Store(root), scenario='blocked')
        mission = runtime.run(runtime.create_research('notice synthetique bloquee', required_pages=1)['id'])
        path = root / 'research-fixture' / 'pauses.sqlite3'
        before = [p['reason'] for p in ResearchPauses(path, create=False).inspect()['pauses'] if p['status'] == 'ACTIVE']
        path.unlink()
        ResearchPauses(path)
        ResearchRuntime(Store(root), scenario='blocked')
        after = ResearchPauses(path, create=False).inspect()['pauses']
        assert before == ['ACCESS_DENIED'], before
        assert after == [], after
        print(json.dumps({'finding': 'G064-3', 'reproduced': True, 'active_before': before,
                          'records_after_replacement': len(after), 'runtime_reopened': True,
                          'synthetic_only': True, 'research_rerun_after_replacement': False}, indent=2))


if __name__ == '__main__':
    main()
