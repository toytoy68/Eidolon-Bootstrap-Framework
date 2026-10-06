# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : html_extract_demo.py
# Description : Extraction HTML bornée sur les pages synthétiques du corpus G007, sans réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Reads the synthetic G007 pages from disk; no network, no JavaScript, no model."""
import argparse
import hashlib
from pathlib import Path

from eidolon_core.contracts import encode
from eidolon_core.html_extract import ExtractLimits, extract
from eidolon_core.presentation import header, message

BODIES = Path(__file__).resolve().parents[1] / 'docs/validation/2026-10-05/claude-g007/bodies'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args(argv)
    results = {}
    for path in sorted(BODIES.glob('*.html')):
        raw = path.read_bytes()
        r = extract(raw)
        assert r['source_sha256'] == hashlib.sha256(raw).hexdigest()
        assert r['text'] is None or r['text_sha256'] == hashlib.sha256(r['text'].encode('utf-8')).hexdigest()
        results[path.name] = {k: r[k] for k in ('status', 'complete', 'title', 'source_sha256', 'text_sha256',
                                                  'segments', 'signals', 'warnings')}
    # Same visible text from two different sources: one text fingerprint, two source fingerprints.
    v2, mirror = results['docs-v2.html'], results['docs-mirror.html']
    assert v2['source_sha256'] != mirror['source_sha256'] and v2['text_sha256'] == mirror['text_sha256']
    partial = extract((BODIES / 'captcha-article.html').read_bytes(), ExtractLimits(output_chars=120))
    assert partial['status'] == 'PARTIAL' and not partial['complete']
    if args.format == 'human':
        print(header(title='Extraction HTML synthétique'))
        print(message('INFO', 'Pages fictives lues sur disque ; aucun réseau, aucun script exécuté.'))
        for name, r in results.items():
            print(message('INFO', f"{name} : {r['status']}, {r['segments']} segment(s), mot de passe={r['signals']['password_field']}"))
        print(message('OK', 'Miroir détecté : empreintes de source différentes, empreinte de texte identique.'))
        print(message('OK', 'Limite de sortie : statut PARTIAL, jamais présenté comme complet.'))
        print(message('ATTENTION', 'Texte externe non fiable ; challenge, login et paywall restent à classer.'))
    else:
        print(encode({'synthetic': True, 'results': results,
                      'partial_example': {k: partial[k] for k in ('status', 'complete', 'warnings', 'segments')}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
