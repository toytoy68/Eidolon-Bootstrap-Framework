# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : download_candidates.py
# Description : Téléchargement explicite d'un manifeste audité, sans exécution de code
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Installation only. Never called by the media service; immutable HF sources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import urllib.request
from urllib.parse import urlsplit


def validate(rows):
    names = set()
    for r in rows:
        if not re.fullmatch(r'[\w-]+/[\w.-]+', r['repo']):
            raise ValueError('repository')
        if not re.fullmatch(r'[a-f0-9]{40}', r['revision']):
            raise ValueError('immutable revision required')
        if not re.fullmatch(r'[a-f0-9]{64}', r['sha256']):
            raise ValueError('checksum required')
        if any(p in ('', '.', '..') for p in r['path'].split('/')) or r['path'].startswith('/'):
            raise ValueError('relative path required')
        if r['name'] != Path(r['path']).name or r['name'] in names:
            raise ValueError('unique basename required')
        if not r['name'].endswith('.safetensors') or type(r['bytes']) is not int or r['bytes'] <= 0:
            raise ValueError('safetensors and exact size required')
        names.add(r['name'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    rows = json.loads(a.manifest.read_text())
    validate(rows)
    a.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    required = sum(r['bytes'] for r in rows if not (a.root/r['name']).exists())
    if shutil.disk_usage(a.root).free < required + 12 * 1024**3:
        raise RuntimeError('DISK_RESERVE_12_GIB')
    for r in rows:
        target = a.root / r['name']
        if target.is_symlink():
            raise RuntimeError('SYMLINK')
        if target.exists():
            with target.open('rb') as f:
                if target.stat().st_size != r['bytes'] or hashlib.file_digest(f, 'sha256').hexdigest() != r['sha256']:
                    raise RuntimeError('EXISTING_CHECKSUM')
            continue
        url = f"https://huggingface.co/{r['repo']}/resolve/{r['revision']}/{r['path']}"
        tmp = target.with_suffix('.partial')
        count = 0
        digest = hashlib.sha256()
        print(json.dumps({'downloading': r['name'], 'bytes': r['bytes']}), flush=True)
        with urllib.request.urlopen(url, timeout=120) as src, tmp.open('xb') as dst:
            host = urlsplit(src.url).hostname
            while block := src.read(8 * 1024**2):
                count += len(block)
                if count > r['bytes']:
                    raise RuntimeError('EXCESS_BYTES')
                digest.update(block)
                dst.write(block)
        if count != r['bytes'] or digest.hexdigest() != r['sha256']:
            raise RuntimeError('CHECKSUM')
        tmp.rename(target)
        target.with_suffix('.receipt.json').write_text(json.dumps({**r, 'initial_url': url, 'download_host': host}, indent=2)+'\n')
        print(json.dumps({'verified': r['name'], 'sha256': r['sha256']}), flush=True)


if __name__ == '__main__':
    main()
