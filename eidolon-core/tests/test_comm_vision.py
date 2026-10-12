# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_vision.py
# Description : Image ponctuelle bornée, présence sans identité, Ollama en boucle locale simulé (G150)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
import threading
import unittest
import zlib

from eidolon_core.comm_contract import CommError
from eidolon_core.comm_vision import OllamaVision, SimulatedVision, Vision, check_image, image_size, observation


def png(width, height):
    raw = b"".join(b"\0" + b"\0\0\0" * width for _ in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def jpeg(width, height):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


class FakeOllama:
    def __init__(self, answer, status=200):
        self.requests, outer = [], self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                outer.requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                if status == 302:
                    self.send_response(302); self.send_header("Location", "http://example.com/"); self.end_headers(); return
                raw = json.dumps({"message": {"content": json.dumps(answer) if not isinstance(answer, str) else answer}}).encode()
                self.send_response(status); self.send_header("Content-Length", str(len(raw))); self.end_headers()
                self.wfile.write(raw)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown(); self.server.server_close()


class ImageTests(unittest.TestCase):
    def test_png_and_jpeg_headers(self):
        self.assertEqual(image_size(png(64, 48)), ("png", 64, 48))
        self.assertEqual(image_size(jpeg(1280, 720)), ("jpeg", 1280, 720))

    def test_refusals(self):
        cases = {"gif": (b"GIF89a" + b"\0" * 20, "INVALID_REQUEST"), "empty": (b"", "INVALID_REQUEST"),
                 "too wide": (jpeg(1920, 1080), "PAYLOAD_TOO_LARGE"),
                 "too big": (b"\xff\xd8" + b"\0" * (2 * 1024 * 1024), "PAYLOAD_TOO_LARGE")}
        for name, (data, code) in cases.items():
            with self.subTest(name):
                with self.assertRaises(CommError) as caught:
                    check_image(data)
                self.assertEqual(caught.exception.code, code)

    def test_model_answers_are_checked(self):
        self.assertEqual(observation({"present": True, "people_count": 2, "description": "Deux\npersonnes\x07."}),
                         {"present": True, "people_count": 2, "description": "Deux personnes ."})
        for bad in ({"present": True, "people_count": 0, "description": "x"},          # inconsistent
                    {"present": "oui", "people_count": 1, "description": "x"},
                    {"present": True, "people_count": 99, "description": "x"}, "texte libre"):
            with self.subTest(bad):
                with self.assertRaises(CommError):
                    observation(bad)


class ServiceTests(unittest.TestCase):
    def test_presence_is_context_never_identity_nor_authorization(self):
        image = png(32, 32)
        vision = Vision(SimulatedVision({hashlib.sha256(image).hexdigest():
                                         {"present": True, "people_count": 1, "description": "Une personne devant l'écran."}}))
        result = vision.describe("pc", image, "presence")
        self.assertEqual((result["present"], result["event"], result["identity"], result["image"]["kept"]),
                         (True, "USER_PRESENT", None, False))
        self.assertEqual((result["unverified"], result["authenticates"], result["authorizes_execution"]),
                         (True, False, False))
        self.assertEqual(vision.describe("pc", png(8, 8), "scene")["event"], "USER_ABSENT")
        self.assertEqual(vision.status()["identification"], "not_available")
        with self.assertRaises(CommError):
            vision.describe("pc", image, "identify")

    def test_ollama_loopback_and_prompt(self):
        fake = FakeOllama({"present": True, "people_count": 1, "description": "Une personne assise."})
        try:
            result = Vision(OllamaVision(fake.endpoint, "gemma3:4b")).describe("pc", jpeg(640, 480), "scene")
            path, body = fake.requests[0]
        finally:
            fake.close()
        self.assertEqual((path, body["model"], body["stream"]), ("/api/chat", "gemma3:4b", False))
        self.assertIn("N'identifie personne", body["messages"][0]["content"])
        self.assertEqual(len(body["messages"][0]["images"]), 1)
        self.assertEqual(result["description"], "Une personne assise.")

    def test_ollama_failures_are_unavailable(self):
        for answer, status in (("pas du json", 200), ({"present": True}, 200), ({}, 500), ({}, 302)):
            with self.subTest(status=status, answer=str(answer)[:15]):
                fake = FakeOllama(answer, status)
                try:
                    with self.assertRaises(CommError) as caught:
                        Vision(OllamaVision(fake.endpoint, "m")).describe("pc", png(8, 8))
                finally:
                    fake.close()
                self.assertEqual(caught.exception.code, "ENGINE_UNAVAILABLE")

    def test_only_a_loopback_endpoint(self):
        for endpoint in ("http://192.168.1.10:11434", "https://127.0.0.1:11434", "http://127.0.0.1",
                         "http://user@127.0.0.1:11434", "http://127.0.0.1:11434/x"):
            with self.subTest(endpoint):
                with self.assertRaises(CommError):
                    OllamaVision(endpoint, "m")


if __name__ == "__main__":
    unittest.main()
