# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_dual_probe.py
# Description : Refus des fausses répartitions et intégrité des poids expérimentaux
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/(name+'.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class DualProbeTests(unittest.TestCase):
    def test_reject_offload_and_single_gpu(self):
        probe = module('flux_dual_probe')
        for mapping in ({'': 0}, {'a': 0, 'transformer_blocks.1': 'cpu'}, {'a': 0, 'b': 1}):
            with self.assertRaises(ValueError):
                probe.validate_map(mapping)
        probe.validate_map({'a': 0, 'transformer_blocks.17': 1})

    def test_corrupt_weight_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'x.safetensors').write_bytes(b'bad')
            with self.assertRaisesRegex(RuntimeError, 'CHECKSUM'):
                module('flux_dual_probe').verify_files(root, [{'name': 'x.safetensors', 'bytes': 3,
                    'sha256': hashlib.sha256(b'yes').hexdigest()}])

    def test_download_path_revision_and_duplicates(self):
        download = module('download_candidates')
        row = {'repo': 'Comfy-Org/model', 'revision': 'a'*40, 'path': 'x.safetensors',
               'name': 'x.safetensors', 'sha256': 'b'*64, 'bytes': 5}
        download.validate([row])
        for change in ({'revision': 'main'}, {'path': '../x.safetensors'}, {'bytes': -1}, {'sha256': ''}):
            with self.assertRaises(ValueError):
                download.validate([{**row, **change}])
        with self.assertRaises(ValueError):
            download.validate([row, row])
