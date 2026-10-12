# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_darme_logo_asset.py
# Description : Logo DARME facultatif servi par Core (identité seulement), page réelle sans lien externe (G176)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import tempfile
import unittest

from eidolon_core import http_api
from eidolon_core.store import Store

TOKEN = "t" * 43
WEB = Path(__file__).resolve().parents[1] / "desktop" / "connected"


class DarmeLogoAssetTests(unittest.TestCase):
    def test_logo_is_served_from_the_real_web_root_as_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            Store(Path(tmp) / "state")
            with http_api.ReadServer(Path(tmp) / "state", TOKEN, port=0, web_root=WEB) as server:
                self.assertIn("/darme-logo.png", server.assets)
                self.assertTrue(server.assets["/darme-logo.png"].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(http_api.ASSETS["/darme-logo.png"][1], "image/png")
        self.assertIn("/darme-logo.png", http_api.OPTIONAL_ASSETS)
        self.assertLess((WEB / "darme-logo.png").stat().st_size, 150 * 1024)   # bounded page weight

    def test_page_references_the_logo_on_its_own_origin_only(self):
        html = (WEB / "index.html").read_text()
        self.assertIn('src="/darme-logo.png"', html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
