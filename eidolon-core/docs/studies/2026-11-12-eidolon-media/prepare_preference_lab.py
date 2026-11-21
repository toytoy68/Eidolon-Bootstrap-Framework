# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_preference_lab.py
# Description : Préparation explicite du laboratoire de préférence isolé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Installation only: verified PyPI wheels and pinned official SDXL configuration.

No existing environment is modified; never called by the media service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.parse
import urllib.request

VERSIONS = {'diffusers':'0.32.2', 'peft':'0.14.0', 'accelerate':'1.3.0',
            'importlib_metadata':'8.6.1', 'zipp':'3.21.0'}
MODEL_REVISION = '462165984030d82259a11f4367a4eed129e94a7b'

def relocate_scripts(source, target):
    """A copied venv's pip/activation scripts must not address the original venv."""
    changed=[]
    for path in (target/'bin').iterdir():
        if path.is_symlink() or not path.is_file():continue
        body=path.read_bytes()
        if b'\0' in body:continue
        updated=body.replace(str(source).encode(),str(target).encode())
        if updated!=body:path.write_bytes(updated);changed.append(path.name)
    return changed

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    import os
    os.umask(0o077)
    target=a.root/'preference-lab';target.mkdir(mode=0o700)
    receipts=[]
    def download(url, dest, expected=None):
        if urllib.parse.urlparse(url).hostname not in ('pypi.org','files.pythonhosted.org','huggingface.co'):
            raise RuntimeError('UNREVIEWED_DOWNLOAD_HOST')
        with urllib.request.urlopen(url,timeout=60) as response:body=response.read(16*1024*1024+1)
        if len(body)>16*1024*1024:raise RuntimeError('DOWNLOAD_TOO_LARGE')
        sha=hashlib.sha256(body).hexdigest()
        if expected is not None and sha!=expected:raise RuntimeError('DOWNLOAD_HASH_MISMATCH')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
        receipts.append({'url':url,'file':str(dest.relative_to(target)),'sha256':sha,'bytes':len(body)})
        return body
    source=a.root/'venv';venv=target/'venv'
    before=subprocess.check_output([str(source/'bin/python'),'-m','pip','freeze'])
    shutil.copytree(source,venv,symlinks=True)
    relocated=relocate_scripts(source,venv)
    wheels=[]
    for name,version in VERSIONS.items():
        meta=json.loads(download(f'https://pypi.org/pypi/{name}/{version}/json',target/'receipts'/f'{name}.json'))
        choices=[x for x in meta['urls'] if x['filename'].endswith('py3-none-any.whl')]
        if len(choices)!=1:raise RuntimeError('AMBIGUOUS_WHEEL')
        item=choices[0];dest=target/'wheels'/item['filename']
        download(item['url'],dest,item['digests']['sha256']);wheels.append(str(dest))
    subprocess.run([str(venv/'bin/python'),'-m','pip','install','--no-index','--no-deps',*wheels],check=True)
    subprocess.run([str(venv/'bin/python'),'-m','pip','check'],check=True)
    paths=['model_index.json','scheduler/scheduler_config.json','text_encoder/config.json',
           'text_encoder_2/config.json','unet/config.json','vae/config.json']
    for tokenizer in ('tokenizer','tokenizer_2'):
        paths += [f'{tokenizer}/{f}' for f in ('merges.txt','special_tokens_map.json','tokenizer_config.json','vocab.json')]
    for name in paths:
        download(f'https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/{MODEL_REVISION}/{name}',target/'sdxl-config'/name)
    after=subprocess.check_output([str(source/'bin/python'),'-m','pip','freeze'])
    if before!=after:raise RuntimeError('SOURCE_ENVIRONMENT_CHANGED')
    (target/'requirements-observed.txt').write_bytes(subprocess.check_output([str(venv/'bin/python'),'-m','pip','freeze']))
    (target/'download-receipts.json').write_text(json.dumps(receipts,indent=2))
    (target/'ready.json').write_text(json.dumps({'source_environment_unchanged':True,
        'source_freeze_sha256':hashlib.sha256(before).hexdigest(),'packages':VERSIONS,
        'model_revision':MODEL_REVISION,'relocated_scripts':relocated}))
    print(json.dumps({'prepared':str(target),'existing_environment_unchanged':True}),flush=True)

if __name__=='__main__':main()
