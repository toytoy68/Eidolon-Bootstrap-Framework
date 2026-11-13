# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_sana_probe.py
# Description : Bornes de recette Sana et conservation des pixels au format écran
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
from pathlib import Path
import sys
import unittest

FOLDER = Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media'
sys.path.insert(0, str(FOLDER))
spec = importlib.util.spec_from_file_location('sana_probe', FOLDER/'sana_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
sys.path.pop(0)


class SanaProbeTests(unittest.TestCase):
    def test_real_sana_cached_embedding_contract_without_gpu(self):
        try:
            import torch
            from diffusers import SanaPipeline
        except ImportError:
            self.skipTest('Sana runtime absent in this workspace')
        from types import SimpleNamespace
        pipe = SimpleNamespace(tokenizer=SimpleNamespace(padding_side='left'),
            text_encoder=None, transformer=SimpleNamespace(dtype=torch.float16))
        e = torch.zeros(1,4,8)
        m = torch.ones(1,4)
        args = dict(prompt=None, prompt_embeds=e, negative_prompt_embeds=e,
                    prompt_attention_mask=m, negative_prompt_attention_mask=m)
        with self.assertRaises(ValueError):
            SanaPipeline.check_inputs(pipe, **args, height=512, width=512, negative_prompt='')
        SanaPipeline.check_inputs(pipe, **args, height=512, width=512, negative_prompt=None)
        actual = SanaPipeline.encode_prompt(pipe, **args, device=torch.device('cpu'), negative_prompt=None)
        self.assertEqual(actual[0].shape,e.shape)
        self.assertEqual(actual[0].dtype,torch.float16)
        self.assertEqual(pipe.tokenizer.padding_side,'right')

    def test_bounded_ramp_and_exact_repeat(self):
        rows = probe.plan()
        self.assertEqual(len(rows), 12)
        self.assertEqual((rows[0]['width'], rows[0]['height']), (512,512))
        self.assertEqual(len([r for r in rows if r['condition']=='native']), 8)
        self.assertEqual({**rows[1], 'condition':'repeat'}, rows[9])
        for r in rows:
            self.assertEqual(r['width']%32, 0)
            self.assertEqual(r['height']%32, 0)
            self.assertLessEqual(r['width']*r['height'], 1024**2)

    def test_padding_preserves_pixels_and_adds_only_side_bars(self):
        from PIL import Image
        im = Image.new('RGB',(768,576),(41,93,177))
        im.putpixel((300,400),(2,5,7))
        result = probe.pad_screen(im)
        self.assertEqual(result.size,(1024,576))
        self.assertEqual(result.crop((128,0,896,576)).tobytes(),im.tobytes())
        self.assertEqual(result.crop((0,0,128,576)).getbbox(),None)
        self.assertEqual(result.crop((896,0,1024,576)).getbbox(),None)
        with self.assertRaises(ValueError):
            probe.pad_screen(Image.new('RGB',(1024,768)))
