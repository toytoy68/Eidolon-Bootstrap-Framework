# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_preference_setup.py
# Description : Isolation des commandes d'un environnement Python copié
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('prepare_preference_lab',Path(__file__).parents[1]/'docs/studies/2026-11-12-eidolon-media/prepare_preference_lab.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class PreferenceSetupTests(unittest.TestCase):
    def test_copied_commands_target_new_environment_without_following_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'old';target=root/'new'
            (source/'bin').mkdir(parents=True);(target/'bin').mkdir(parents=True)
            original=b'#!'+str(source).encode()+b'/bin/python\n'
            (source/'bin/pip').write_bytes(original)
            (target/'bin/pip').write_bytes(original)
            (target/'bin/pip').chmod(0o755)
            (target/'bin/link').symlink_to(source/'bin/pip')
            (target/'bin/binary').write_bytes(b'\0'+original)
            self.assertEqual(setup.relocate_scripts(source,target),['pip'])
            self.assertIn(str(target).encode(),(target/'bin/pip').read_bytes())
            self.assertEqual((source/'bin/pip').read_bytes(),original)
            self.assertEqual((target/'bin/binary').read_bytes(),b'\0'+original)
            self.assertEqual((target/'bin/pip').stat().st_mode&0o777,0o755)

if __name__=='__main__':unittest.main()
