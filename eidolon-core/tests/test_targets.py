# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_targets.py
# Description : Tests du catalogue pur de cibles et capacités
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic catalog tests. No network, DNS, share or personal file is used."""
import copy
import socket
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.targets import Catalog


def config():
    return {"schema": "targets/1", "targets": [
        {"id": "docs-web", "name": "Documentation publique", "kind": "web_public",
         "destination": "https://docs.example.invalid/",
         "capabilities": [{"name": "web.read", "effect": "egress_read"}]},
        {"id": "nas-main", "name": "NAS principal", "kind": "nas_storage", "aliases": ["NAS", "stockage"],
         "destination": "smb://nas-main.example.invalid/archives",
         "capabilities": [{"name": "files.list", "effect": "local_read", "scope": {"roots": ["archives"]}},
                          {"name": "files.read", "effect": "local_read", "scope": {"roots": ["archives"]}}],
         "secret_refs": {"credential": "nas-main-reader"}},
        {"id": "nas-backup", "name": "NAS de sauvegarde", "kind": "nas_storage", "aliases": ["nas"],
         "capabilities": [{"name": "files.list", "effect": "local_read"}]},
        {"id": "memory-engine", "name": "Memory Engine", "kind": "lan_service", "aliases": ["mémoire"],
         "capabilities": [{"name": "memory.recall", "effect": "local_read"},
                          {"name": "service.restart", "effect": "mutation"}]},
        {"id": "pc-session", "name": "Session Windows", "kind": "windows_session",
         "capabilities": [{"name": "files.search", "effect": "local_read",
                           "scope": {"folders": ["Documents", "Images"]}}]},
    ]}


class TargetCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog.from_config(config())

    def test_resolution_by_id_and_alias_is_stable_and_normalized(self):
        for reference in ("memory-engine", "Memory-Engine", "  mémoire ", "MÉMOIRE"):
            found = self.catalog.resolve(reference)
            self.assertEqual((found.status, found.target.id), ("FOUND", "memory-engine"), reference)
        self.assertEqual(self.catalog.resolve("stockage").target.id, "nas-main")

    def test_ambiguous_alias_never_picks_a_candidate(self):
        found = self.catalog.resolve("nas")  # alias of nas-main ("NAS") and of nas-backup
        self.assertEqual(found.status, "TARGET_AMBIGUOUS")
        self.assertIsNone(found.target)
        self.assertEqual(found.candidates, ("nas-backup", "nas-main"))
        self.assertEqual(self.catalog.lookup("nas", "files.list").status, "TARGET_AMBIGUOUS")

    def test_absent_target_and_absent_capability_are_distinct(self):
        self.assertEqual(self.catalog.resolve("routeur").status, "TARGET_ABSENT")
        lookup = self.catalog.lookup("nas-backup", "files.read")
        self.assertEqual(lookup.status, "CAPABILITY_ABSENT")
        self.assertEqual(lookup.target.id, "nas-backup")
        self.assertIsNone(lookup.capability)
        found = self.catalog.lookup("nas-main", "files.read")
        self.assertEqual((found.status, found.capability.effect), ("FOUND", "local_read"))

    def test_model_strings_are_data_not_commands(self):
        for reference in ("rm -rf /", "https://169.254.169.254/latest", "../../etc/passwd", "nas; reboot"):
            self.assertEqual(self.catalog.resolve(reference).status, "TARGET_ABSENT", reference)
        for bad in (None, 3, {"id": "nas-main"}, "x" * 201, "nas​", "nas\n"):
            with self.assertRaises(ContractError, msg=repr(bad)):
                self.catalog.resolve(bad)

    def test_duplicate_and_conflicting_identities_are_refused(self):
        duplicated = config()
        duplicated["targets"].append(copy.deepcopy(duplicated["targets"][0]))
        clash = config()
        clash["targets"][2]["aliases"] = ["nas-main"]  # alias equal to another id
        twice = config()
        twice["targets"][1]["capabilities"].append({"name": "files.read", "effect": "local_read"})
        for case in (duplicated, clash, twice):
            with self.assertRaises(ContractError):
                Catalog.from_config(case)

    def test_malformed_configuration_is_refused(self):
        def variant(change):
            value = config()
            change(value)
            return value
        cases = [
            variant(lambda c: c["targets"][0]["capabilities"][0].update(effect="read")),
            variant(lambda c: c["targets"][0]["capabilities"][0].update(effect=None)),
            variant(lambda c: c["targets"][0].update(kind="internet")),
            variant(lambda c: c["targets"][0].update(id="Docs Web")),
            variant(lambda c: c["targets"][0].update(shell="curl x")),
            variant(lambda c: c["targets"][0]["capabilities"][0].update(name="read")),
            variant(lambda c: c["targets"][0]["capabilities"][0].update(scope=["a"])),
            variant(lambda c: c["targets"][0]["capabilities"][0].update(scope={"x": "y" * 5000})),
            variant(lambda c: c["targets"][0].update(aliases=["a%d" % i for i in range(17)])),
            variant(lambda c: c["targets"].extend(
                {"id": "t%d" % i, "name": "t", "kind": "lan_service"} for i in range(64))),
            variant(lambda c: c.update(schema="targets/2")),
            variant(lambda c: c.update(extra=True)),
            variant(lambda c: c["targets"][0].update(name="")),
        ]
        for case in cases:
            with self.assertRaises(ContractError):
                Catalog.from_config(case)

    def test_secret_references_are_names_never_values(self):
        manifest = self.catalog.manifest()
        nas = next(t for t in manifest["targets"] if t["id"] == "nas-main")
        self.assertEqual(nas["secret_refs"], {"credential": "nas-main-reader"})
        for value in ("admin:hunter2", "smb://user:pw@nas", "token with spaces", "/etc/secret", ""):
            case = config()
            case["targets"][1]["secret_refs"] = {"credential": value}
            with self.assertRaises(ContractError, msg=value):
                Catalog.from_config(case)

    def test_manifest_and_fingerprint_ignore_configuration_order(self):
        reordered = config()
        reordered["targets"].reverse()
        for target in reordered["targets"]:
            target.get("aliases", []).reverse()
            target["capabilities"].reverse()
        other = Catalog.from_config(reordered)
        self.assertEqual(other.manifest(), self.catalog.manifest())
        self.assertEqual(other.fingerprint(), self.catalog.fingerprint())

    def test_fingerprint_changes_with_destination_capability_or_effect(self):
        base = self.catalog.fingerprint()
        changes = [
            lambda c: c["targets"][1].update(destination="smb://other.example.invalid/archives"),
            lambda c: c["targets"][1]["capabilities"].pop(),
            lambda c: c["targets"][3]["capabilities"][0].update(effect="egress_read"),
            lambda c: c["targets"][1]["capabilities"][0]["scope"].update(roots=["archives", "photos"]),
            lambda c: c["targets"][1].update(secret_refs={"credential": "nas-main-admin"}),
            lambda c: c["targets"][2]["aliases"].append("backup"),
        ]
        for change in changes:
            value = config()
            change(value)
            self.assertNotEqual(Catalog.from_config(value).fingerprint(), base)

    def test_catalog_performs_no_network_access(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("network access attempted")
        with patch.object(socket, "socket", forbidden), patch.object(socket, "getaddrinfo", forbidden), \
                patch.object(socket, "create_connection", forbidden):
            catalog = Catalog.from_config(config())
            catalog.lookup("docs-web", "web.read")
            catalog.lookup("nas", "files.read")
            catalog.fingerprint()

    def test_declared_capability_is_not_a_permission(self):
        restart = self.catalog.lookup("memory-engine", "service.restart")
        self.assertEqual((restart.status, restart.capability.effect), ("FOUND", "mutation"))
        self.assertFalse(hasattr(restart.capability, "allowed"))
        self.assertNotIn("allowed", str(self.catalog.manifest()))


if __name__ == "__main__":
    unittest.main()
