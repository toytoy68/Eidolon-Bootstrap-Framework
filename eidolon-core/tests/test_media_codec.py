# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_codec.py
# Description : Export vidéo CPU réel, aucun GPU ni modèle simulé comme réel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from fractions import Fraction
import importlib.util
import io
import unittest
from eidolon_core.media_agents import MediaError
from eidolon_core.media_service import encode_mp4

@unittest.skipUnless(importlib.util.find_spec('av'), 'optional PyAV runtime required')
class CodecTests(unittest.TestCase):
    def source(self):
        import av
        out=io.BytesIO()
        with av.open(out,'w',format='webm') as c:
            s=c.add_stream('libvpx-vp9',rate=8); s.width=64; s.height=64; s.pix_fmt='yuv420p'
            for i in range(17):
                frame=av.VideoFrame(64,64,'yuv420p')
                for plane in frame.planes: plane.update(bytes([20+i*5])*plane.buffer_size)
                frame.pts=i; frame.time_base=Fraction(1,8)
                for packet in s.encode(frame): c.mux(packet)
            for packet in s.encode(): c.mux(packet)
        return out.getvalue()
    def test_export_preserves_fps_duration_and_frame_count(self):
        import av
        data=encode_mp4(self.source(),{'width':64,'height':64,'frames':17,'fps':8})
        with av.open(io.BytesIO(data)) as c:
            s=c.streams.video[0]
            self.assertEqual(s.average_rate,8)
            self.assertAlmostEqual(float(s.duration*s.time_base),2.125)
            self.assertEqual(len(list(c.decode(video=0))),17)
    def test_truncated_video_rejected(self):
        with self.assertRaisesRegex(MediaError,'FRAME_COUNT_MISMATCH'):
            encode_mp4(self.source(),{'width':64,'height':64,'frames':18,'fps':8})
    def test_geometry_mismatch_rejected(self):
        with self.assertRaisesRegex(MediaError,'VIDEO_GEOMETRY_MISMATCH'):
            encode_mp4(self.source(),{'width':128,'height':64,'frames':17,'fps':8})

if __name__=='__main__':unittest.main()
