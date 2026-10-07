# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : query_history_demo.py
# Description : Relecture de requêtes synthétiques, sans réseau ni état persistant utilisateur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with PYTHONPATH=src; temporary local data and zero network operations."""
from tempfile import TemporaryDirectory
from eidolon_core.contracts import encode
from eidolon_core.query_history import read_history
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard


class Provider:
    provider_id = "synthetic-provider/1"

    def search(self, query, limit):
        return []


class Reader:
    reader_id = "synthetic-reader/1"

    def read(self, *args):
        raise AssertionError("No page expected in the empty synthetic provider")


def no_dns(*args):
    raise AssertionError("No DNS expected")


def main():
    with TemporaryDirectory(prefix="eidolon-history-demo-") as root:
        guard = ResearchGuard(root, retain_queries=True)
        coordinator = ResearchCoordinator([Provider()], Reader(), resolver=no_dns, guard=guard)
        for query in ("notice jean@example.invalid 198.51.100.7:25565", "jean@example.invalid"):
            coordinator.run(query)
        print(encode(read_history(guard)))


if __name__ == "__main__":
    main()
