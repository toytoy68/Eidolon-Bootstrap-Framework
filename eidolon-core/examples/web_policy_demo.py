# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : web_policy_demo.py
# Description : Démonstration des décisions Web, DNS entièrement synthétique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Exercise destination decisions without opening a socket or a mission."""
import argparse
from dataclasses import asdict

from eidolon_core.contracts import encode
from eidolon_core.egress import WebPolicy, decide, follow
from eidolon_core.presentation import header, message, section


# Classification fixtures only: none describes toytoy's household or is queried.
DNS = {"public.example": ["9.9.9.9"], "household.example": ["8.8.8.8"],
       "household-v6.example": ["2001:4860:4860::8888"],
       "mixed.example": ["9.9.9.9", "192.168.50.10"]}


def resolve(host, port):
    return DNS[host]


def scenarios():
    policy = WebPolicy(blocked_networks=("8.8.8.8", "2001:4860::/32"))
    start = decide("https://public.example/start", resolve, policy)
    checks = [
        ("public", start, "ALLOWED"),
        ("private-lan", decide("https://192.168.50.10/", resolve, policy), "DESTINATION_NOT_GLOBAL"),
        ("household-public-ip", decide("https://household.example/", resolve, policy), "DESTINATION_BLOCKED_NETWORK"),
        ("household-ipv6", decide("https://household-v6.example/", resolve, policy), "DESTINATION_BLOCKED_NETWORK"),
        ("mixed-dns", decide("https://mixed.example/", resolve, policy), "DESTINATION_NOT_GLOBAL"),
        ("redirect-household", follow(start, "https://household.example/", resolve, policy), "DESTINATION_BLOCKED_NETWORK"),
        ("redirect-control", follow(start, "/pa\nge", resolve, policy), "BAD_URL"),
        ("relative-redirect", follow(start, "/next", resolve, policy), "ALLOWED"),
    ]
    for name, decision, expected in checks:
        if decision.code != expected or decision.allowed != (expected == "ALLOWED"):
            raise AssertionError(f"unexpected decision for {name}")
        yield {"scenario": name, "synthetic": True, "expected_code": expected,
               "checked": True, "decision": asdict(decision),
               "scope": "destination policy only; no DNS, HTTP, model or mission execution"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    if args.format == "human":
        print(header(title="Politique Web simulée"))
        print(message("INFO", "Huit décisions avec DNS synthétique ; aucun accès réseau."))
        print(section("Vérification des décisions"))
    for result in scenarios():
        if args.format == "human":
            print(message("OK", f"Décision attendue vérifiée : {result['scenario']} → {result['decision']['code']}"))
        else:
            print(encode(result))
    if args.format == "human":
        print(message("ATTENTION", "ALLOWED ne prouve ni une connexion ni une mission réussie."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
