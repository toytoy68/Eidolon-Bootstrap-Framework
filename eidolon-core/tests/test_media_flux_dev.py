# Eidolon Core / Eidolon Core Technologies (ECT)
# Numerical compatibility tests for the G338 research attention processor.
import importlib.util
import os
from pathlib import Path
import unittest

class FluxDevAttentionTests(unittest.TestCase):
    def compare(self,device,dtype):
        import torch
        from diffusers import FluxTransformer2DModel
        path=Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media/flux_chunked_attention.py'
        spec=importlib.util.spec_from_file_location('flux_chunks',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        torch.manual_seed(123);torch.set_num_threads(2)
        torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_math_sdp(True)
        model=FluxTransformer2DModel(patch_size=1,in_channels=4,out_channels=4,num_layers=1,num_single_layers=1,attention_head_dim=16,num_attention_heads=2,joint_attention_dim=8,pooled_projection_dim=4,guidance_embeds=True,axes_dims_rope=(4,6,6)).to(device=device,dtype=dtype).eval()
        args=dict(hidden_states=torch.randn(1,19,4,device=device,dtype=dtype),encoder_hidden_states=torch.randn(1,7,8,device=device,dtype=dtype),pooled_projections=torch.randn(1,4,device=device,dtype=dtype),timestep=torch.tensor([.5],device=device,dtype=dtype),guidance=torch.tensor([3.5],device=device,dtype=dtype),txt_ids=torch.zeros(7,3,device=device,dtype=dtype),img_ids=torch.arange(57,device=device,dtype=dtype).reshape(19,3),return_dict=False)
        with torch.inference_mode():
            before=model(**args)[0]
            model.set_attn_processor(mod.ChunkedFluxAttnProcessor(5))
            after=model(**args)[0]
        tolerance=3e-3 if dtype==torch.float16 else 3e-5
        torch.testing.assert_close(after,before,atol=tolerance,rtol=tolerance)
        self.assertTrue(torch.isfinite(after).all())
        with self.assertRaisesRegex(ValueError,'CHUNK_SIZE'):mod.ChunkedFluxAttnProcessor(0)
        with self.assertRaisesRegex(ValueError,'MASK_UNSUPPORTED'):mod.ChunkedFluxAttnProcessor()(None,None,attention_mask=True)
        print('comparison',device,str(dtype),'max_abs',float((after-before).abs().max()))
    def test_full_transformer_fp32(self):
        import torch
        self.compare('cpu',torch.float32)
    @unittest.skipUnless(os.environ.get('EIDOLON_TEST_V100')=='1','explicit V100 test required')
    def test_full_transformer_v100_fp16(self):
        import torch
        self.assertEqual(torch.cuda.get_device_capability(0),(7,0))
        self.compare('cuda:0',torch.float16)
