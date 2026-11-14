# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : feedback_collect.py
# Description : Lot de collecte de préférences à géométrie constante
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Reuse the measured, guarded runner; no automatic aesthetic scoring."""
import quality_probe as probe

def plan():
    cases = {
        'hand': probe.CASES['hand'],
        'two_objects': ('Studio photograph of one red ceramic mug on the left and one blue '
                        'ceramic bowl on the right, separated on a grey table. Both objects '
                        'fully visible, soft side lighting.'),
        'katana': probe.CASES['katana'],
    }
    result = []
    # Distinct from G328 and its untouched confirmation seeds.
    for case, prompt in cases.items():
        for seed in (40961, 65537, 786433, 999983):
            request = probe.validate(dict(profile='sdxl-text', prompt=prompt,
                seed=seed, steps=30, width=1024, height=1024))
            result.append(dict(case=case, request=request,
                               expected_graph=probe.workflow(request, prefix='qualityprobe')))
    return result

if __name__ == '__main__':
    probe.plan = plan
    probe.main()
