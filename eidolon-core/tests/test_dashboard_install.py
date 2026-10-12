# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_dashboard_install.py
# Description : Prévol et installation préparée du dashboard dans une racine temporaire : rien d'écrasé, ports cohérents (G159)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import importlib.util
import json
import os
from pathlib import Path
import socket
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / "deployment" / "vm-profile"
_spec = importlib.util.spec_from_file_location("dashboard_install", HERE / "deployment" / "dashboard_install.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)

ACTIVE_CORE = """[Unit]
Description=Eidolon Core (copie active de la VM, différente du dépôt)
[Service]
User=toytoy
ExecStart=/opt/x/.venv/bin/python -m eidolon_core.http_api --state /home/toytoy/eidolon-beta/state --port 8767 --local-flag kept
Environment=LOCAL=1
"""


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "etc/systemd/system").mkdir(parents=True)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_simulation_changes_nothing(self):
        (self.root / "etc/systemd/system/eidolon-core-api.service").write_text(ACTIVE_CORE)
        before = self.snapshot()
        actions, archive = D.install(SOURCE, self.root)
        self.assertIsNone(archive)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([a[0] for a in actions], ["créer", "créer", "compléter", "créer 0600"])

    def test_apply_keeps_the_active_core_unit_and_adds_only_the_relay_flags(self):
        core = self.root / "etc/systemd/system/eidolon-core-api.service"
        core.write_text(ACTIVE_CORE)
        actions, archive = D.install(SOURCE, self.root, apply=True)
        text = core.read_text()
        self.assertIn("--local-flag kept --comm-port 8766 --monitor-port 8768", text)
        self.assertIn("Environment=LOCAL=1", text)
        self.assertEqual(text.replace(" --comm-port 8766 --monitor-port 8768", ""), ACTIVE_CORE)
        with tarfile.open(archive) as tar:
            self.assertEqual(tar.getnames(), ["etc/systemd/system/eidolon-core-api.service"])
            self.assertEqual(tar.extractfile(tar.getnames()[0]).read().decode(), ACTIVE_CORE)
        self.assertEqual(oct(os.stat(archive).st_mode & 0o777), "0o600")
        config = self.root / D.PATHS["monitor_config"]
        self.assertEqual(oct(os.stat(config).st_mode & 0o777), "0o600")
        self.assertEqual(json.loads(config.read_text())["machines"][0]["socket"], "/run/eidolon-darme/status.sock")
        # Second run: nothing to change, no second archive.
        self.assertEqual({a[0] for a in D.install(SOURCE, self.root, apply=True)[0]}, {"identique", "conserver"})
        self.assertEqual(len(list((self.root / D.PATHS["backup"]).iterdir())), 1)

    def test_existing_configuration_is_never_overwritten(self):
        config = self.root / D.PATHS["monitor_config"]
        config.parent.mkdir(parents=True)
        config.write_text('{"mine": true}')
        D.install(SOURCE, self.root, apply=True)
        self.assertEqual(config.read_text(), '{"mine": true}')

    def test_refusals_symlink_and_conflicting_port(self):
        core = self.root / "etc/systemd/system/eidolon-core-api.service"
        core.write_text(ACTIVE_CORE.replace("--port 8767", "--port 8767 --comm-port 9999"))
        with self.assertRaisesRegex(ValueError, "CORE_UNIT_CONFLICT"):
            D.install(SOURCE, self.root, apply=True)
        core.unlink()
        (self.root / "etc/systemd/system/eidolon-monitor.service").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ValueError, "REFUSED_SYMLINK"):
            D.install(SOURCE, self.root, apply=True)
        self.assertFalse((self.root / D.PATHS["backup"]).exists())


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dpf"); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "etc/systemd/system").mkdir(parents=True)
        for unit in D.UNITS:
            (self.root / "etc/systemd/system" / unit).write_bytes((SOURCE / unit).read_bytes())
        for name, value in (("monitor_config", json.loads((SOURCE / "monitor.json.example").read_text())),
                            ("comm_config", {"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"}})):
            path = self.root / D.PATHS[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value)); os.chmod(path, 0o600)
        (self.root / "run/eidolon-darme").mkdir(parents=True)
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(self.root / "run/eidolon-darme/status.sock"))
        self.addCleanup(self.sock.close)

    def failed(self):
        return [c["check"] for c in D.preflight(self.root, owner="nobody-here") if not c["ok"]]

    def test_repository_profile_is_consistent(self):
        self.assertEqual(self.failed(), [])

    def test_mismatched_port_open_config_and_wrong_origin_are_reported(self):
        unit = self.root / "etc/systemd/system/eidolon-monitor.service"
        unit.write_text(unit.read_text().replace("--port 8768", "--port 8769"))
        config = self.root / D.PATHS["monitor_config"]
        value = json.loads(config.read_text()); value["allowed_origin"] = "http://127.0.0.1:8765"
        config.write_text(json.dumps(value)); os.chmod(config, 0o644)
        failed = self.failed()
        self.assertIn("Core relaie vers le bon port surveillance", failed)
        self.assertTrue(any("privé" in c for c in failed))
        self.assertTrue(any("origine" in c for c in failed))

    def test_missing_engines_config_and_socket_are_reported(self):
        (self.root / D.PATHS["comm_config"]).unlink()
        self.sock.close(); (self.root / "run/eidolon-darme/status.sock").unlink()
        failed = self.failed()
        self.assertIn("comm.json présent", failed)
        self.assertIn("socket DARME /run/eidolon-darme/status.sock", failed)


if __name__ == "__main__":
    unittest.main()
