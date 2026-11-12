# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_display.py
# Description : Proportions, bordures et limites des formats écran
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import io
import unittest
from PIL import Image
from eidolon_core.media_agents import MediaError
from eidolon_core.media_display import fit, fit_png, canvas_size
from eidolon_core.media_profiles import validate, workflow

class DisplayTests(unittest.TestCase):
    def test_wide_generation_is_exact_16_9_and_normalization_stable(self):
        for profile in ('sd15-text','wan21-text','svd-image'):
            value={'profile':profile,'format':'16:9','output_size':'1080p'}
            if profile=='svd-image':value['source']={'private':'reference'}
            r=validate(value)
            self.assertEqual(r['width']*9,r['height']*16)
            self.assertEqual(validate(r),r)
            self.assertEqual(canvas_size(r),(1920,1080))
    def test_pillarbox_generation_is_4_3_not_a_cropped_wide_frame(self):
        r=validate({'format':'4:3-pillarbox'})
        self.assertEqual(r['width']*3,r['height']*4)
        g=workflow(r,prefix='frame')
        self.assertEqual(g['4']['inputs']['width'],r['width'])
        self.assertEqual(canvas_size(r),(768,432))
    def test_black_borders_are_exactly_240_pixels_at_1080p(self):
        image=fit(Image.new('RGB',(576,432),'white'),(1920,1080))
        self.assertEqual(image.getbbox(),(240,0,1680,1080))
        self.assertEqual(image.crop((0,0,240,1080)).getbbox(),None)
        self.assertEqual(image.crop((1680,0,1920,1080)).getbbox(),None)
    def test_source_fit_preserves_portrait_content_without_stretch_or_crop(self):
        image=fit(Image.new('RGB',(100,200),'white'),(512,288))
        self.assertEqual(image.getbbox(),(184,0,328,288))
    def test_mask_padding_stays_black_and_binary(self):
        image=fit(Image.new('RGB',(4,3),'white'),(512,288),mask=True)
        self.assertEqual(set(image.getdata()),{(0,0,0),(255,255,255)})
    def test_bad_display_options_and_conflicting_geometry_rejected(self):
        for value in ({'format':'21:9'},{'format':[]},{'output_size':'8k'},
                      {'output_size':'1080p'},{'format':'16:9','width':512},
                      {'format':'16:9','height':432.0}):
            with self.subTest(value=value),self.assertRaises(MediaError):validate(value)
    def test_png_export_checks_source_geometry(self):
        b=io.BytesIO();Image.new('RGB',(576,432),'white').save(b,format='PNG')
        out=fit_png(b.getvalue(),(1280,720),expected=(576,432))
        with Image.open(io.BytesIO(out)) as im:self.assertEqual(im.getbbox(),(160,0,1120,720))
        with self.assertRaisesRegex(MediaError,'IMAGE_GEOMETRY_MISMATCH'):
            fit_png(b.getvalue(),(1280,720),expected=(768,432))

if __name__=='__main__':unittest.main()
