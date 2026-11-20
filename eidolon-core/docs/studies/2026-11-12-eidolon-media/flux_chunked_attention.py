# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : flux_chunked_attention.py
# Description : Attention FLUX par blocs de requetes, sans approximation des cles
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Research processor matching Diffusers 0.32.2 FluxAttnProcessor2_0.
All keys/values remain visible to every query. No global backend monkeypatch.
"""
import torch
from torch.nn import functional as F
from diffusers.models.embeddings import apply_rotary_emb

class ChunkedFluxAttnProcessor:
    def __init__(self, chunk_size=256):
        if not isinstance(chunk_size,int) or chunk_size<1:raise ValueError('CHUNK_SIZE')
        self.chunk_size=chunk_size

    def __call__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, image_rotary_emb=None):
        if attention_mask is not None:raise ValueError('MASK_UNSUPPORTED')
        batch=hidden_states.shape[0]
        def heads(t):return t.view(batch,-1,attn.heads,t.shape[-1]//attn.heads).transpose(1,2)
        q,k,v=[heads(layer(hidden_states)) for layer in (attn.to_q,attn.to_k,attn.to_v)]
        if attn.norm_q is not None:q=attn.norm_q(q)
        if attn.norm_k is not None:k=attn.norm_k(k)
        count=0
        if encoder_hidden_states is not None:
            count=encoder_hidden_states.shape[1]
            cq,ck,cv=[heads(layer(encoder_hidden_states)) for layer in (attn.add_q_proj,attn.add_k_proj,attn.add_v_proj)]
            if attn.norm_added_q is not None:cq=attn.norm_added_q(cq)
            if attn.norm_added_k is not None:ck=attn.norm_added_k(ck)
            q,k,v=[torch.cat((a,b),dim=2) for a,b in ((cq,q),(ck,k),(cv,v))]
        if image_rotary_emb is not None:
            q=apply_rotary_emb(q,image_rotary_emb);k=apply_rotary_emb(k,image_rotary_emb)
        out=torch.cat([F.scaled_dot_product_attention(q[:,:,i:i+self.chunk_size],k,v,dropout_p=0.0,is_causal=False) for i in range(0,q.shape[2],self.chunk_size)],dim=2)
        out=out.transpose(1,2).reshape(batch,-1,attn.heads*q.shape[-1]).to(q.dtype)
        if encoder_hidden_states is None:return out
        context,image=out[:,:count],out[:,count:]
        return attn.to_out[1](attn.to_out[0](image)),attn.to_add_out(context)
