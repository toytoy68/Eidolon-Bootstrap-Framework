# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_animatediff_probe.py
# Description : Bornes vidéo, refus non-fini et aller-retour MP4
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
FOLDER=Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media'
sys.path.insert(0,str(FOLDER))
spec=importlib.util.spec_from_file_location('animatediff_probe',FOLDER/'animatediff_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe);sys.path.pop(0)

class AnimateDiffProbeTests(unittest.TestCase):
    def test_progressive_budget_and_repeat(self):
        rows=probe.plan();self.assertEqual(len(rows),6);self.assertEqual(rows[0]['frames'],8)
        self.assertEqual({**rows[1],'condition':'repeat'},rows[3])
        for r in rows:
            self.assertLessEqual(r['width']*r['height']*r['frames'],512*512*16)
            self.assertEqual(r['width']%8,0);self.assertEqual(r['height']%8,0)
            self.assertLessEqual(r['frames']/r['fps'],2)
        self.assertEqual(rows[4]['width']*9,rows[4]['height']*16)
    def test_nonfinite_rejected_before_clamp(self):
        import numpy as np
        for x in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaisesRegex(ValueError,'NONFINITE'):probe.decoded_to_uint8(np.array([x]))
        self.assertEqual(probe.decoded_to_uint8(np.array([-2.,-1.,0.,1.,2.])).tolist(),[0,0,128,255,255])
    def test_real_mp4_roundtrip_and_invalid_shape(self):
        try:import av
        except ImportError:self.skipTest('PyAV absent')
        import numpy as np
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'video.mp4';frames=[np.full((32,64,3),i*20,dtype=np.uint8) for i in range(8)]
            r=probe.save_video(frames,p,8);self.assertEqual((r['frames'],r['width'],r['height'],r['codec'],r['duration_s']),(8,64,32,'h264',1.0))
            with self.assertRaisesRegex(ValueError,'SHAPE'):probe.save_video([frames[0],frames[1][:,:32]],p,8)
            with self.assertRaisesRegex(ValueError,'SHAPE'):probe.save_video([f.astype(float) for f in frames],p,8)

    def test_real_motion_unet_slicing_preserves_small_forward(self):
        try:
            import torch
            from diffusers import UNetMotionModel
        except ImportError:self.skipTest('Diffusers absent')
        torch.manual_seed(7);torch.set_num_threads(2)
        model=UNetMotionModel(block_out_channels=(32,),down_block_types=('CrossAttnDownBlockMotion',),up_block_types=('CrossAttnUpBlockMotion',),cross_attention_dim=32,num_attention_heads=4,norm_num_groups=8,motion_num_attention_heads=4,layers_per_block=1).eval()
        x=torch.randn(1,4,4,8,8);text=torch.randn(4,8,32)
        with torch.no_grad():
            before=model(x,1,encoder_hidden_states=text).sample
            processors=probe.configure_attention(model)
            after=model(x,1,encoder_hidden_states=text).sample
        self.assertIn('SlicedAttnProcessor',processors.values())
        self.assertIn('AttnProcessor2_0',processors.values())
        torch.testing.assert_close(after,before,atol=2e-5,rtol=2e-5)
