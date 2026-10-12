# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_profile_plan.py
# Description : Contrats du plan privé des profils et refus d'activation G170-A
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from dataclasses import FrozenInstanceError
import unittest

from eidolon_core.profile_plan import POLICY, ProfilePlanError, validate_profile_plan


def fixture():
    return {"schema": "eidolon-user-profile-plan/1", "status": "PLANNED_NOT_ACTIVE",
            "created_at": "2026-10-12T12:00:00+02:00", "source": "synthetic test",
            "runtime_importer_implemented": False,
            "profiles": [
                {"profile_id": "user-001", "display_name": "Operator",
                 "given_name": "Alex", "aliases": ["Operator", "Alex"], "role": "admin"},
                {"profile_id": "user-002", "display_name": "Visitor A", "role": "casual"},
                {"profile_id": "user-003", "display_name": "Visitor B", "role": "casual"}],
            "policy": dict(POLICY)}


class ProfilePlanTests(unittest.TestCase):
    def test_three_profiles_are_prepared_without_runtime_rights(self):
        plan = validate_profile_plan(fixture())
        self.assertEqual([p.role for p in plan.profiles], ["admin", "casual", "casual"])
        self.assertEqual(plan.summary()["profiles"], 3)
        self.assertFalse(plan.summary()["runtime_active"])
        self.assertNotIn("Operator", str(plan.summary()))

    def test_result_is_detached_and_immutable(self):
        data = fixture()
        plan = validate_profile_plan(data)
        data["profiles"][0]["aliases"].append("Changed")
        self.assertEqual(plan.profiles[0].aliases, ("Operator", "Alex"))
        with self.assertRaises(FrozenInstanceError):
            plan.profiles[1].role = "admin"

    def test_no_activation_or_secret_field_can_be_smuggled_in(self):
        for key, val in [("status", "ACTIVE"), ("runtime_importer_implemented", True),
                         ("password", "not-a-real-secret"), ("token", "fake")]:
            data = fixture(); data[key] = val
            with self.subTest(key=key), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_policy_must_preserve_no_capture_no_biometric_authorization(self):
        for key, val in [("capture_enabled", True), ("biometric_authorization", True),
                         ("casual_admin_permissions", True), ("capture_enabled", 0),
                         ("memory_scope_default", "shared")]:
            data = fixture(); data["policy"][key] = val
            with self.subTest(key=key, value=val), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_ids_and_roles_are_validated(self):
        for key, val in [("profile_id", "../admin"), ("profile_id", "user-001"),
                         ("role", "root"), ("role", True), ("permissions", ["sudo"])]:
            data = fixture(); data["profiles"][1][key] = val
            with self.subTest(key=key, value=val), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_exactly_one_admin_is_required(self):
        for role_index, role in [(0, "casual"), (1, "admin")]:
            data = fixture(); data["profiles"][role_index]["role"] = role
            with self.subTest(role=role), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_profile_id_boundaries_are_shared_with_identity_consumers(self):
        from eidolon_core.profile_plan import PROFILE_ID
        for identifier in ("a", "a" * 64):
            data = fixture(); data["profiles"][0]["profile_id"] = identifier
            self.assertIsNotNone(PROFILE_ID.fullmatch(identifier))
            self.assertEqual(validate_profile_plan(data).profiles[0].profile_id, identifier)
        for identifier in ("", "1a", "A", "a" * 65, "a/b"):
            data = fixture(); data["profiles"][0]["profile_id"] = identifier
            self.assertIsNone(PROFILE_ID.fullmatch(identifier))
            with self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_alias_collision_uses_case_and_unicode_normalization(self):
        for name in ["operator", "Ｏｐｅｒａｔｏｒ"]:
            data = fixture(); data["profiles"][1]["aliases"] = [name]
            with self.subTest(name=name), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_duplicate_aliases_and_malformed_names_are_refused(self):
        for key, val in [("aliases", "Visitor"), ("aliases", ["A", "a"]),
                         ("display_name", " hidden "), ("display_name", "A\u200bB"),
                         ("display_name", "A\nB"), ("display_name", ""), ("given_name", None)]:
            data = fixture(); data["profiles"][1][key] = val
            with self.subTest(key=key, value=val), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_missing_and_unknown_fields_are_refused(self):
        for key in fixture():
            data = fixture(); del data[key]
            with self.subTest(key=key), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)
        with self.assertRaises(ProfilePlanError):
            validate_profile_plan(None)

    def test_date_must_be_valid_and_timezone_aware(self):
        for value in [None, 123, "invalid", "2026-10-12T12:00:00"]:
            data = fixture(); data["created_at"] = value
            with self.subTest(value=value), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_count_is_explicit_for_bootstrap_plan(self):
        for count in [0, 1, 2, 4]:
            data = fixture()
            data["profiles"] = [copy.deepcopy(data["profiles"][0]) for _ in range(count)]
            with self.subTest(count=count), self.assertRaises(ProfilePlanError):
                validate_profile_plan(data)

    def test_failed_validation_does_not_mutate_input(self):
        data = fixture(); data["profiles"][1]["role"] = "admin"
        before = copy.deepcopy(data)
        with self.assertRaises(ProfilePlanError):
            validate_profile_plan(data)
        self.assertEqual(data, before)
