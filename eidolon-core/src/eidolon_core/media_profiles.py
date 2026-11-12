# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_profiles.py
# Description : Profils ComfyUI bornés pour la recette V100
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Trusted workflow builders; callers cannot supply nodes, models or paths."""
from .media_agents import MediaError

PROFILES = {
    'sd15-text': {'kind': 'image', 'source': False, 'model': 'SD1.5', 'license': 'CreativeML OpenRAIL-M'},
    'sd15-edit': {'kind': 'image', 'source': True, 'model': 'SD1.5', 'license': 'CreativeML OpenRAIL-M'},
    'sd15-inpaint': {'kind': 'image', 'source': True, 'model': 'SD1.5', 'license': 'CreativeML OpenRAIL-M'},
    'wan21-text': {'kind': 'video', 'source': False, 'model': 'Wan2.1 T2V 1.3B', 'license': 'Apache-2.0'},
    'svd-image': {'kind': 'video', 'source': True, 'model': 'SVD 14 frames', 'license': 'Stability Community 2024-07-05'},
}

def validate(value):
    if type(value) is not dict or set(value) - {'profile', 'prompt', 'seed', 'steps', 'width', 'height', 'frames', 'fps', 'denoise', 'source', 'mask', 'checkpoint', 'loras'}:
        raise MediaError('INVALID_REQUEST')
    r = dict(profile='sd15-text', prompt='', seed=42, steps=20, width=512, height=512,
             frames=9, fps=8, denoise=0.6)
    r.update(value)
    if r['profile'] not in PROFILES:
        raise MediaError('UNKNOWN_PROFILE')
    profile = PROFILES[r['profile']]
    if not isinstance(r['prompt'], str) or len(r['prompt'].encode()) > 4000:
        raise MediaError('INVALID_PROMPT')
    for key, lo, hi in [('seed', 0, 2**32-1), ('steps', 1, 40), ('width', 256, 768),
                        ('height', 256, 768), ('frames', 5, 25), ('fps', 1, 24)]:
        if type(r[key]) is not int or not lo <= r[key] <= hi:
            raise MediaError('INVALID_' + key.upper())
    if r['width'] % 64 or r['height'] % 64:
        raise MediaError('INVALID_GEOMETRY')
    if profile['kind'] == 'video' and (r['width'] > 512 or r['height'] > 320):
        raise MediaError('VIDEO_BUDGET_EXCEEDED')
    if r['profile'] == 'wan21-text' and r['frames'] % 4 != 1:
        raise MediaError('INVALID_FRAME_COUNT')
    if r['profile'] == 'svd-image' and r['frames'] > 14:
        raise MediaError('INVALID_FRAME_COUNT')
    if type(r['denoise']) not in (int, float) or not 0 < r['denoise'] <= 1:
        raise MediaError('INVALID_DENOISE')
    if bool(r.get('source')) != profile['source']:
        raise MediaError('SOURCE_MISMATCH')
    if bool(r.get('mask')) != (r['profile'] == 'sd15-inpaint'):
        raise MediaError('MASK_MISMATCH')
    if 'checkpoint' in r or 'loras' in r:
        import re
        if not r['profile'].startswith('sd15'): raise MediaError('MODEL_SELECTION_PROFILE_MISMATCH')
        if 'checkpoint' in r and (not isinstance(r['checkpoint'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',r['checkpoint'])):
            raise MediaError('INVALID_MODEL_ID')
        loras=r.get('loras',[])
        if type(loras) is not list or len(loras)>2: raise MediaError('LORA_LIMIT')
        for lora in loras:
            if type(lora) is not dict or set(lora)!={'id','strength'} or not isinstance(lora['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',lora['id']):
                raise MediaError('INVALID_LORA')
            if type(lora['strength']) not in (int,float) or not 0<=lora['strength']<=1:
                raise MediaError('INVALID_LORA_STRENGTH')
    # References are validated by the existing ArtifactStore before execution.
    return r

def workflow(request, *, prefix, source_name=None, mask_name=None):
    r = validate(request)
    def node(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}
    if not prefix.isalnum() or len(prefix) > 64:
        raise MediaError('INVALID_PREFIX')
    for name in (source_name, mask_name):
        if name is not None and (not name.endswith('.png') or not name[:-4].isalnum()):
            raise MediaError('INVALID_STAGED_NAME')
    p = r['profile']
    if p.startswith('sd15'):
        g = {
            '1': node('CheckpointLoaderSimple', ckpt_name='v1-5-pruned-emaonly.safetensors'),
            '2': node('CLIPTextEncode', text=r['prompt'], clip=['1', 1]),
            '3': node('CLIPTextEncode', text='blurry, distorted, text, watermark', clip=['1', 1]),
            '4': node('EmptyLatentImage', width=r['width'], height=r['height'], batch_size=1),
            '5': node('KSampler', model=['1', 0], positive=['2', 0], negative=['3', 0],
                      latent_image=['4', 0], seed=r['seed'], steps=r['steps'], cfg=7.0,
                      sampler_name='euler', scheduler='normal', denoise=1.0),
            '6': node('VAEDecode', samples=['5', 0], vae=['1', 2]),
            '7': node('SaveImage', images=['6', 0], filename_prefix=prefix),
        }
        if p != 'sd15-text':
            g['8'] = node('LoadImage', image=source_name)
            g['9'] = node('ImageScale', image=['8', 0], upscale_method='bicubic',
                          width=r['width'], height=r['height'], crop='disabled')
            g['4'] = node('VAEEncode', pixels=['9', 0], vae=['1', 2])
            g['5']['inputs']['denoise'] = r['denoise']
        if p == 'sd15-inpaint':
            g['10'] = node('LoadImageMask', image=mask_name, channel='red')
            g['4'] = node('VAEEncodeForInpaint', pixels=['9', 0], vae=['1', 2], mask=['10', 0], grow_mask_by=6)
            g['11'] = node('ImageCompositeMasked', destination=['9', 0], source=['6', 0],
                           x=0, y=0, resize_source=False, mask=['10', 0])
            g['7']['inputs']['images'] = ['11', 0]
        return g
    if p == 'wan21-text':
        g = {
            '1': node('UNETLoader', unet_name='wan2.1_t2v_1.3B_fp16.safetensors', weight_dtype='default'),
            '2': node('CLIPLoader', clip_name='umt5_xxl_fp16.safetensors', type='wan', device='default'),
            '3': node('VAELoader', vae_name='wan_2.1_vae.safetensors'),
            '4': node('CLIPTextEncode', text=r['prompt'], clip=['2', 0]),
            '5': node('CLIPTextEncode', text='blurry, static, distorted, text, watermark', clip=['2', 0]),
            '6': node('EmptyHunyuanLatentVideo', width=r['width'], height=r['height'], length=r['frames'], batch_size=1),
            '7': node('ModelSamplingSD3', model=['1', 0], shift=8.0),
            '8': node('KSampler', model=['7', 0], positive=['4', 0], negative=['5', 0],
                      latent_image=['6', 0], seed=r['seed'], steps=r['steps'], cfg=6.0,
                      sampler_name='uni_pc', scheduler='simple', denoise=1.0),
        }
        vae = ['3', 0]
    else:
        g = {
            '1': node('ImageOnlyCheckpointLoader', ckpt_name='svd.safetensors'),
            '2': node('LoadImage', image=source_name),
            '3': node('SVD_img2vid_Conditioning', clip_vision=['1', 1], init_image=['2', 0], vae=['1', 2],
                      width=r['width'], height=r['height'], video_frames=r['frames'], motion_bucket_id=80,
                      fps=r['fps'], augmentation_level=0.0),
            '7': node('VideoLinearCFGGuidance', model=['1', 0], min_cfg=1.0),
            '8': node('KSampler', model=['7', 0], positive=['3', 0], negative=['3', 1],
                      latent_image=['3', 2], seed=r['seed'], steps=r['steps'], cfg=2.5,
                      sampler_name='euler', scheduler='karras', denoise=1.0),
        }
        vae = ['1', 2]
    g['9'] = node('VAEDecodeTiled', samples=['8', 0], vae=vae, tile_size=256, overlap=64,
                  temporal_size=8, temporal_overlap=4)
    g['10'] = node('SaveWEBM', images=['9', 0], filename_prefix=prefix, codec='vp9', fps=float(r['fps']), crf=20.0)
    return g
