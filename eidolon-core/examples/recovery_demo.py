# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recovery_demo.py
# Description : Accord ancien copié pour revue, sans autorité d'exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic approved action and an isolated historical recovery copy."""
import argparse
from pathlib import Path
import tempfile

from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import ContractError, encode
from eidolon_core.presentation import header, message
from eidolon_core.recovery import inspect_review, prepare_review
from eidolon_core.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='eidolon-recovery-') as directory:
        source = Store(Path(directory) / 'source')
        runtime = ActionRuntime(source)
        mission = runtime.run(runtime.create_restart('nas')['id'])
        runtime.decide(mission['id'], expected_sha256=mission['proposal']['sha256'], decision='approve',
                       actor='synthetic-operator', reason='approved synthetic proposal before recovery')
        target = Path(directory) / 'review'
        before = source.path.read_bytes()
        report = prepare_review(source.path, target, actor='synthetic-operator', reason='restoration rehearsal')
        historical = inspect_review(target, mission_id=mission['id'])
        assert historical['mission']['proposal_status_at_snapshot'] == 'APPROVED'
        assert not historical['execution_authority']
        assert report['store_id'] != report['source_store_id']
        try:
            Store(target)
        except ContractError as exc:
            assert str(exc).startswith('RECOVERY_REVIEW_ONLY')
            blocked = str(exc)
        else:
            raise AssertionError('a historical copy must not open as a runtime store')
        assert source.path.read_bytes() == before
        assert runtime.world.observe('sim-nas')['restarts'] == 0
        result = {'synthetic': True, 'report': historical, 'runtime_refusal': blocked,
                  'source_unchanged': True, 'simulated_restarts': 0}
        if args.format == 'json':
            print(encode(result))
        else:
            print(header(title='Restauration préparée pour revue') + '\n'.join([
                message('OK', 'Copie historique cohérente créée ; source inchangée.'),
                message('OK', 'Identité renouvelée ; démarrage de Core refusé sur cette copie.'),
                message('ATTENTION', 'Ancien accord APPROVED conservé comme historique, sans autorité d’exécution.'),
                message('INFO', 'Zéro redémarrage fictif ; réactivation non implémentée.')]))


if __name__ == '__main__':
    main()
