# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : download_models.py
# Description : Installation explicite de poids identifiés, jamais appelée par le service
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run only during installation. Immutable revisions and upstream LFS SHA256.

SD1.5: CreativeML OpenRAIL-M. Wan: Apache-2.0. SVD: Stability Community
2024-07-05 (personal/non-commercial evaluation here; not an unrestricted license).
No downloaded Python, pickle, extension or installer is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit

MODELS = [
    ('sd15', 'stable-diffusion-v1-5/stable-diffusion-v1-5', '451f4fe16113bff5a5d2269ed5ad43b0592e9a14', 'v1-5-pruned-emaonly.safetensors', 'checkpoints', '6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa', 4265146304),
    ('wan', 'Comfy-Org/Wan_2.1_ComfyUI_repackaged', '123acf1cc74bccbb9bfff8ac1ee72edc08c2341d', 'split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors', 'diffusion_models', 'be531024cd9018cb5b48c40cfbb6a6191645b1c792eb8bf4f8c1c6e10f924dc5', 2838303560),
    ('wan', 'Comfy-Org/Wan_2.1_ComfyUI_repackaged', '123acf1cc74bccbb9bfff8ac1ee72edc08c2341d', 'split_files/text_encoders/umt5_xxl_fp16.safetensors', 'text_encoders', '7b8850f1961e1cf8a77cca4c964a358d303f490833c6c087d0cff4b2f99db2af', 11366399385),
    ('wan', 'Comfy-Org/Wan_2.1_ComfyUI_repackaged', '123acf1cc74bccbb9bfff8ac1ee72edc08c2341d', 'split_files/vae/wan_2.1_vae.safetensors', 'vae', '2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b', 253815318),
    ('svd', 'stabilityai/stable-video-diffusion-img2vid', '9cf024d5bfa8f56622af86c884f26a52f6676f2e', 'svd.safetensors', 'checkpoints', '3e0994626df395a3831de024f11b2d9d241143bb6f16e2efbacced248aa18ce0', 9559625980),
]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--profile', choices=['sd15', 'wan', 'svd'], required=True)
    args = p.parse_args()
    for profile, repo, rev, name, directory, expected, size in MODELS:
        if profile != args.profile:
            continue
        target = args.root / directory / Path(name).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            with target.open('rb') as f:
                assert hashlib.file_digest(f, 'sha256').hexdigest() == expected
            print('verified existing', target.name, flush=True)
            continue
        url = f'https://huggingface.co/{repo}/resolve/{rev}/{name}'
        part = target.with_suffix('.partial')
        digest = hashlib.sha256()
        print('downloading', target.name, size, flush=True)
        with urllib.request.urlopen(url, timeout=120) as src, part.open('xb') as dst:
            final_host = urlsplit(src.url).hostname
            count = 0
            while block := src.read(8 * 1024 * 1024):
                count += len(block)
                if count > size:
                    raise ValueError('unexpected size')
                digest.update(block)
                dst.write(block)
        assert count == size and digest.hexdigest() == expected, 'checksum mismatch'
        part.rename(target)
        receipt = dict(repo=repo, revision=rev, path=name, sha256=expected, bytes=size,
                       download_host=final_host, initial_url=url)
        target.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print('verified', target.name, expected, flush=True)

if __name__ == '__main__':
    main()
