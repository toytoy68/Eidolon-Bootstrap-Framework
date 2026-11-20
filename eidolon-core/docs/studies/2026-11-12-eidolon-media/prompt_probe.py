# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prompt_probe.py
# Description : Comparaison bornee de formulations, moteur et seeds constants
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G331: paired prompt tests, not a training or general quality validation."""
import quality_probe as probe
import feedback_collect

SEEDS = (20261113, 20261114)
DETAILED = {
    'hand': ('A single studio photograph of one adult right hand, palmar view, '
             'palm facing the camera and fingers pointing up. Four fingers and one thumb, '
             'each separate and naturally attached to the palm. Thumb on the left. '
             'Natural finger joints, subtle skin creases, relaxed spread fingers. '
             'The entire hand and wrist visible against a plain grey background.'),
    'two_objects': ('A single studio product photograph showing exactly two separate objects '
                    'on a grey table: one entirely red ceramic mug with a handle on the left, '
                    'and one entirely blue round ceramic bowl with a smooth rim and no handle '
                    'on the right. Empty space between the objects. Both fully in frame, '
                    'soft side lighting.'),
    'katana': ('A single overhead product photograph of exactly two separate objects '
               'on grey fabric: one complete Japanese katana and one empty black lacquer '
               'scabbard lying parallel beside it. The katana has one continuous curved '
               'steel blade attached to one black wrapped handle through one small gold '
               'guard. The entire sword, blade tip, handle and scabbard are inside the frame. '
               'The scabbard is long enough to cover the blade. Fine gold fittings.'),
}

def plan():
    originals = {e['case']: e['request']['prompt'] for e in feedback_collect.plan()}
    result = []
    for case in ('hand', 'two_objects', 'katana'):
        for i, seed in enumerate(SEEDS):
            # Counterbalance order; all twelve trials are reported, no seed selection.
            variants = ('original', 'detailed') if i == 0 else ('detailed', 'original')
            for variant in variants:
                prompt = originals[case] if variant == 'original' else DETAILED[case]
                request = probe.validate(dict(profile='sdxl-text', prompt=prompt,
                    seed=seed, steps=30, width=1024, height=1024))
                result.append(dict(case=case+'_'+variant, request=request,
                    expected_graph=probe.workflow(request, prefix='qualityprobe')))
    return result

if __name__ == '__main__':
    probe.plan = plan
    probe.main()
