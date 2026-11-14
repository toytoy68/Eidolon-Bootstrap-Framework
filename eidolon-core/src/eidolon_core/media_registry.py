# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_registry.py
# Description : Catalogue local de checkpoints et LoRA vérifiés par l'opérateur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Generic SD1.5 model selection; no download or remotely configurable policy.

License text/source and intended uses are operator-reviewed metadata, not an
automated legal conclusion. Hashes bind entries to local safetensors bytes.
No specialized content-generation policy is implemented here.
"""
import hashlib
from pathlib import Path
import re
from .media_agents import MediaError, load_json

class ModelRegistry:
    def __init__(self, document, models_root):
        if type(document) is not dict or set(document) != {'schema','entries'} or document['schema'] != 'eidolon-media-models/1':
            raise MediaError('INVALID_MODEL_REGISTRY')
        entries = document['entries']
        if type(entries) is not dict or len(entries) > 64: raise MediaError('INVALID_MODEL_REGISTRY')
        self.entries = {}
        root = Path(models_root)
        if root.is_symlink() or not root.is_dir(): raise MediaError('INVALID_MODEL_ROOT')
        for key, entry in entries.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key) or type(entry) is not dict:
                raise MediaError('INVALID_MODEL_ENTRY')
            required = {'type','family','filename','sha256','license','source','approved_uses','reviewed'}
            if set(entry) != required or entry['type'] not in {'checkpoint','lora'} or entry['family'] != 'sd15' or entry['reviewed'] is not True:
                raise MediaError('MODEL_REVIEW_REQUIRED')
            if not isinstance(entry['filename'], str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,160}\.safetensors',entry['filename']) or '..' in entry['filename']:
                raise MediaError('INVALID_MODEL_FILE')
            if not re.fullmatch(r'[0-9a-f]{64}',entry['sha256']): raise MediaError('INVALID_MODEL_HASH')
            if not all(isinstance(entry[x],str) and 1 <= len(entry[x]) <= 1000 for x in ['license','source']):
                raise MediaError('LICENSE_PROVENANCE_REQUIRED')
            if not isinstance(entry['approved_uses'],list) or not entry['approved_uses'] or not all(isinstance(x,str) and 1 <= len(x) <= 120 for x in entry['approved_uses']):
                raise MediaError('APPROVED_USES_REQUIRED')
            folder = root / ('checkpoints' if entry['type']=='checkpoint' else 'loras')
            path = folder/entry['filename']
            if folder.is_symlink() or path.is_symlink() or not path.is_file(): raise MediaError('MODEL_FILE_UNAVAILABLE')
            with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual != entry['sha256']: raise MediaError('MODEL_HASH_MISMATCH')
            self.entries[key] = dict(entry)

    def validate(self, request):
        ids = ([request['checkpoint']] if 'checkpoint' in request else []) + [x['id'] for x in request.get('loras', [])]
        for model_id in ids:
            if model_id not in self.entries: raise MediaError('MODEL_NOT_REGISTERED')
        if 'checkpoint' in request and self.entries[request['checkpoint']]['type'] != 'checkpoint':
            raise MediaError('MODEL_TYPE_MISMATCH')
        if any(self.entries[x['id']]['type']!='lora' for x in request.get('loras',[])):
            raise MediaError('MODEL_TYPE_MISMATCH')

    def apply(self, graph, request):
        self.validate(request)
        if 'checkpoint' in request: graph['1']['inputs']['ckpt_name']=self.entries[request['checkpoint']]['filename']
        model, clip = ['1',0], ['1',1]
        for i, selected in enumerate(request.get('loras', [])):
            node=str(20+i)
            graph[node]={'class_type':'LoraLoader','inputs':{'model':model,'clip':clip,
                'lora_name':self.entries[selected['id']]['filename'],
                'strength_model':selected['strength'],'strength_clip':selected['strength']}}
            model,clip=[node,0],[node,1]
        if request.get('loras'):
            graph['5']['inputs']['model']=model
            graph['2']['inputs']['clip']=clip;graph['3']['inputs']['clip']=clip
        return graph
