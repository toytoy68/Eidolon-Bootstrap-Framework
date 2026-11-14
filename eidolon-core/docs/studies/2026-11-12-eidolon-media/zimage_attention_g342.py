# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : zimage_attention_g342.py
# Description : Attention FP32 par tranches de requêtes, sans changer les clés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Local inference-only adapter for ZImage's B,S,H,D attention dispatch."""
import torch
import torch.nn.functional as F
from torch.nn.attention import sdpa_kernel, SDPBackend

def chunked_attention(query,key,value,attn_mask=None,dropout_p=0.0,is_causal=False,backend=None,parallel_config=None,**kwargs):
    if dropout_p or is_causal or parallel_config is not None or kwargs:
        raise ValueError('Unsupported attention option')
    q,k,v=(x.transpose(1,2) for x in (query,key,value))
    result=[]
    with sdpa_kernel(SDPBackend.MATH):
        for start in range(0,q.shape[-2],256):
            mask=attn_mask
            if mask is not None and mask.shape[-2]!=1:
                mask=mask[...,start:start+256,:]
            result.append(F.scaled_dot_product_attention(q[...,start:start+256,:],k,v,attn_mask=mask,dropout_p=0.,is_causal=False))
    return torch.cat(result,dim=-2).transpose(1,2)

def verify():
    from diffusers.models.transformers.transformer_z_image import dispatch_attention_fn
    results=[]
    for device in ['cpu','cuda:0','cuda:1']:
        g=torch.Generator(device).manual_seed(342)
        q,k,v=[torch.randn((1,513,4,32),device=device,generator=g) for _ in range(3)]
        for kind in ['none','padding','full']:
            mask=None
            if kind!='none':
                mask=torch.ones((1,1,1 if kind=='padding' else 513,513),device=device,dtype=torch.bool)
                mask[...,-7:]=False
            with sdpa_kernel(SDPBackend.MATH):
                ref=dispatch_attention_fn(q,k,v,attn_mask=mask,dropout_p=0.,is_causal=False)
                got=chunked_attention(q,k,v,attn_mask=mask)
            torch.testing.assert_close(got,ref,atol=2e-6,rtol=2e-5)
            assert torch.isfinite(got).all()
            results.append({'device':device,'mask':kind,'max_abs':(got-ref).abs().max().item()})
    return results

if __name__=='__main__':
    import json
    print(json.dumps(verify(),indent=2))
