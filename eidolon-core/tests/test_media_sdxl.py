# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_sdxl.py
# Description : Contrats SDXL isolés, distincts de la recette matérielle
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import unittest
from eidolon_core.media_agents import MediaError
from eidolon_core.media_display import canvas_size
from eidolon_core.media_profiles import validate, workflow

class SDXLTests(unittest.TestCase):
    def test_native_and_wide_have_separate_bounded_geometry(self):
        square=validate({'profile':'sdxl-text'})
        self.assertEqual((square['width'],square['height']),(1024,1024))
        wide=validate({'profile':'sdxl-text','format':'16:9'})
        self.assertEqual((wide['width'],wide['height']),(1024,576))
        self.assertEqual(validate(wide),wide)
    def test_four_thirds_canvas_preserves_ratio(self):
        r=validate({'profile':'sdxl-text','format':'4:3-pillarbox'})
        self.assertEqual((r['width'],r['height']),(768,576))
        self.assertEqual(canvas_size(r),(1024,576))
    def test_dimensions_and_foreign_model_selection_refused(self):
        for request in ({'width':1088},{'height':True},{'checkpoint':'sd15'},
                        {'loras':[{'id':'sd15-lora','strength':.5}]},{'source':'image'}):
            with self.subTest(request=request),self.assertRaises(MediaError):
                validate({'profile':'sdxl-text',**request})
    def test_sdxl_uses_two_text_inputs_and_matching_size_conditioning(self):
        g=workflow({'profile':'sdxl-text','format':'16:9','prompt':'castle'},prefix='test')
        self.assertEqual(g['1']['inputs']['ckpt_name'],'sd_xl_base_1.0.safetensors')
        for key in ('2','3'):
            self.assertEqual(g[key]['class_type'],'CLIPTextEncodeSDXL')
            self.assertEqual(g[key]['inputs']['target_width'],1024)
            self.assertEqual(g[key]['inputs']['target_height'],576)
            self.assertEqual(g[key]['inputs']['text_g'],g[key]['inputs']['text_l'])
        self.assertEqual(g['5']['inputs']['sampler_name'],'dpmpp_2m')
        self.assertNotIn('LoadImage',[n['class_type'] for n in g.values()])
    def test_sd15_budget_and_sampler_unchanged(self):
        with self.assertRaises(MediaError):validate({'width':1024})
        r=validate({'format':'16:9'});self.assertEqual((r['width'],r['height']),(768,432))
        self.assertEqual(workflow(r,prefix='test')['5']['inputs']['sampler_name'],'euler')

if __name__=='__main__':unittest.main()
