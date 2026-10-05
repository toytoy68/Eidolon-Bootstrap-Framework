# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_demo.py
# Description : Recherche Eidolon synthétique avec repli, cache et blocages
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""No external service, DNS, model or dependency; all sources are fabricated."""
import argparse
from dataclasses import dataclass

from eidolon_core.contracts import encode
from eidolon_core.presentation import header, message
from eidolon_core.research import AccessFailure, Hit, Page, ResearchCoordinator


@dataclass(frozen=True)
class FixtureProvider:
    provider_id: str
    blocked: bool = False

    def search(self, query, limit):
        if self.blocked:
            raise AccessFailure("RATE_LIMITED", 60)
        return [Hit("https://sources.example/manual", "Manuel synthétique", "Extrait du moteur, pas une preuve."),
                Hit("https://sources.example/challenge", "Source inaccessible", "Extrait à ne pas citer comme lecture.")][:limit]


class FixtureReader:
    reader_id = "research-demo-reader/1"
    def __init__(self): self.calls = 0
    def read(self, url, policy):
        self.calls += 1
        if url.endswith("challenge"):
            return Page(url, 200, "text/html", b"<title>Verify you are human</title>", policy.policy_id)
        return Page(url, 200, "text/plain", "Document synthétique : ne pas activer un service sans accord.".encode(), policy.policy_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    reader = FixtureReader()
    coordinator = ResearchCoordinator([FixtureProvider("primary", True), FixtureProvider("fallback")], reader,
                                      resolver=lambda host, port: ["9.9.9.9"])
    if args.format == "human":
        print(header(title="Recherche Web simulée"))
        print(message("INFO", "Sources entièrement fictives, aucun réseau ni modèle."))
    for label, target, expected in [("fallback",1,"READ_TARGET_MET"), ("cached",1,"READ_TARGET_MET"),
                                    ("partial",2,"PARTIAL")]:
        result = coordinator.run("Chercher une référence synthétique", required_pages=target)
        if result["status"] != expected:
            raise AssertionError("unexpected research outcome")
        if label == "cached" and (not result["sources"][0]["cache_hit"] or reader.calls != 1):
            raise AssertionError("cache did not avoid the duplicate read")
        if label == "partial" and result["sources"][1]["state"] != "CHALLENGE_SUSPECTED":
            raise AssertionError("challenge was mistaken for readable content")
        if args.format == "human":
            print(message("OK", f"Scénario {label} vérifié : {result['status']}, {result['readable_pages']} texte(s) lu(s)."))
            for source in result["sources"]:
                print(message("INFO", f"{source['state']} | cache={source['cache_hit']} | {source['url']}"))
        else:
            print(encode({"scenario": label, "synthetic": True, "report": result}))
    if args.format == "human":
        print(message("ATTENTION", "Un texte lu ne confirme pas ses affirmations ; HTML général et réseau réel restent à intégrer."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
