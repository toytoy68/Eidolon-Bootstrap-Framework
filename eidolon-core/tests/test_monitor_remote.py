# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_monitor_remote.py
# Description : Canal Memory → dashboard : SSH à arguments fixes, hôte épinglé, réponse bornée, commande forcée (G166)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from eidolon_core import monitor_remote as R
from eidolon_core.monitor_service import MonitorAPI, load_config

HERE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("darme_status_feed", HERE / "deployment/memory-feed/darme_status_feed.py")
FEED = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FEED)

STATUS = {"service_schema": "eidolon-darme-service/1", "badge": "grey", "visibility": "partial",
          "sources": {"memory-bridge.service": True}, "authorizes_execution": False,
          "generated_at": "2026-10-12T10:00:00+00:00"}
FAKE_SSH = '''#!{python}
import json, sys, time
from pathlib import Path
Path(__file__).with_name("argv.json").write_text(json.dumps(sys.argv[1:]))
host = sys.argv[-1]
if host == "ok": print({status!r})
elif host == "big": sys.stdout.write("x" * 200000)
elif host == "slow": time.sleep(30)
elif host == "garbage": print("not json")
else: sys.exit(255)
'''


class RemoteReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.key, self.known = root / "id_ed25519", root / "known_hosts"
        self.key.write_text("private"); os.chmod(self.key, 0o600)
        self.known.write_text("memory ssh-ed25519 AAAA"); os.chmod(self.known, 0o644)
        self.ssh = root / "ssh"
        self.ssh.write_text(FAKE_SSH.format(python=sys.executable, status=json.dumps(STATUS)))
        os.chmod(self.ssh, 0o700)

    def spec(self, host="ok", **changes):
        value = {"host": host, "user": "eidolon-monitor-feed", "key": str(self.key), "known_hosts": str(self.known)}
        value.update(changes)
        return R.validate(value)

    def test_fixed_command_line_with_pinned_host_and_nothing_else(self):
        self.assertEqual(R.read_ssh(self.spec(), ssh=str(self.ssh)), (STATUS, None))
        argv = json.loads((self.ssh.parent / "argv.json").read_text())
        self.assertEqual(argv[-3:], ["eidolon-monitor-feed", "--", "ok"])
        for option in ("BatchMode=yes", "StrictHostKeyChecking=yes", "UserKnownHostsFile=" + str(self.known),
                       "IdentitiesOnly=yes", "IdentityAgent=none", "ForwardAgent=no", "ClearAllForwardings=yes",
                       "PermitLocalCommand=no", "ControlPath=none"):
            self.assertIn(option, argv)
        self.assertEqual(argv[:4], ["-F", "/dev/null", "-T", "-n"])
        self.assertEqual(argv.count("--"), 1)                       # no remote command after the host

    def test_bounded_size_time_and_generic_errors(self):
        self.assertEqual(R.read_ssh(self.spec("big"), ssh=str(self.ssh)), (None, "REPLY_TOO_LARGE"))
        started = time.monotonic()
        self.assertEqual(R.read_ssh(self.spec("slow"), ssh=str(self.ssh), timeout=0.5), (None, "TIMEOUT"))
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(R.read_ssh(self.spec("garbage"), ssh=str(self.ssh)), (None, "INVALID_REPLY"))
        self.assertEqual(R.read_ssh(self.spec("refused"), ssh=str(self.ssh)), (None, "UNAVAILABLE"))
        self.assertEqual(R.read_ssh(self.spec(), ssh=str(self.ssh.parent / "absent")), (None, "UNAVAILABLE"))

    def test_configuration_refusals(self):
        for host in ("-oProxyCommand=x", "a b", "a;b", "", "x" * 300):
            with self.assertRaises(ValueError, msg=host):
                self.spec(host)
        for changes in ({"user": "Root"}, {"user": "-l"}, {"port": 0}, {"port": "22"}, {"command": "id"}):
            with self.assertRaises(ValueError, msg=changes):
                self.spec(**changes)
        os.chmod(self.key, 0o640)
        with self.assertRaisesRegex(ValueError, "NOT_PRIVATE"):
            self.spec()
        os.chmod(self.key, 0o600)
        os.chmod(self.known, 0o666)
        with self.assertRaisesRegex(ValueError, "known_hosts"):
            self.spec()
        os.chmod(self.known, 0o644)
        link = self.key.with_name("link"); link.symlink_to(self.key)
        with self.assertRaisesRegex(ValueError, "NOT_PRIVATE"):
            self.spec(key=str(link))

    def test_monitor_config_and_one_ssh_read_per_ten_seconds(self):
        config = Path(self.tmp.name) / "monitor.json"
        config.write_text(json.dumps({"schema": "eidolon-monitor-config/1", "machines": [
            {"id": "memory", "label": "Memory", "ssh": {"host": "memory", "user": "eidolon-monitor-feed",
                                                       "key": str(self.key), "known_hosts": str(self.known)}}]}))
        os.chmod(config, 0o600)
        machines = load_config(config)["machines"]
        calls = []
        status = dict(STATUS, generated_at=datetime.now(timezone.utc).isoformat())

        def remote(spec):
            calls.append(spec["host"])
            return status, None
        api = MonitorAPI(None, machines, remote_reader=remote, cache_seconds=0)
        for _ in range(4):
            entry = api.status()["machines"][0]
        self.assertEqual((entry["state"], entry["darme"]["badge"], calls), ("ok", "grey", ["memory"]))
        for bad in ({"ssh": {"host": "memory"}}, {"ssh": {**machines[0]["ssh"], "host": "-x"}}):
            config.write_text(json.dumps({"schema": "eidolon-monitor-config/1",
                                          "machines": [{"id": "memory", "label": "Memory", **bad}]}))
            with self.assertRaises(ValueError):
                load_config(config)


class ForcedCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "status.sock")
        self.server = socket.socket(socket.AF_UNIX); self.server.bind(self.path); self.server.listen(2)
        self.addCleanup(self.server.close)
        self.requests = []

        def run():
            while True:
                try:
                    connection, _ = self.server.accept()
                except OSError:
                    return
                with connection:
                    self.requests.append(connection.recv(65))
                    try:
                        connection.sendall(json.dumps(STATUS).encode() + b"\n")
                    except OSError:
                        pass
        threading.Thread(target=run, daemon=True).start()

    def test_one_line_from_the_expected_server_only(self):
        self.assertEqual(json.loads(FEED.feed(self.path, expected_uid=os.getuid())), STATUS)
        with self.assertRaises(ValueError):
            FEED.feed(self.path, expected_uid=os.getuid() + 1)
        # The refused peer may or may not have been accepted yet by the server thread: it sent nothing.
        self.assertEqual([r for r in self.requests if r], [b"STATUS\n"])

    def test_any_client_command_is_refused(self):
        script = HERE / "deployment/memory-feed/darme_status_feed.py"
        for env, args in (({"SSH_ORIGINAL_COMMAND": "cat /etc/shadow"}, []), ({}, ["--socket", "/tmp/x"])):
            done = subprocess.run([sys.executable, "-I", str(script), *args], env=env, capture_output=True,
                                  text=True, timeout=10)
            self.assertEqual((done.returncode, done.stdout.strip()), (2, '{"error":"FEED_TAKES_NO_COMMAND"}'))


if __name__ == "__main__":
    unittest.main()
