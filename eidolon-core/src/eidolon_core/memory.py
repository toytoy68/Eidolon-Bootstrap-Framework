# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : memory.py
# Description : Interfaces de rappel mémoire, sans mutation métier
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Read-only ports. The optional adapter delegates to the real engine API."""
from dataclasses import asdict, dataclass
from pathlib import Path

from .contracts import snapshot

DEMO_REQUEST = "Calculer les statistiques du texte synthétique de démonstration."
DEMO_TEXT = "Ne pas acheter la V100 cette semaine. Ceci est une donnée synthétique."


@dataclass(frozen=True)
class SyntheticMemory:
    provider_id: str = "synthetic-memory/1"

    def recall(self, query):
        return {"query": query, "policy_version": self.provider_id,
                "excluded_counts": {}, "items": [{
                    "information_id": "synthetic-note", "revision": 1,
                    "content": DEMO_TEXT, "epistemic_status": "UNVERIFIED",
                    "operational_state": "PLANNED", "confidence": "LOW",
                    "needs_review": True, "truncated": False,
                    "excerpt_reference": {"source": "fixture/1", "start": 0, "end": len(DEMO_TEXT)},
                    "provenance": {"source": "synthetic-fixture", "kind": "original_source"},
                    "verification": {}, "temporal": {}, "relations": [],
                    "applicability": "UNKNOWN",
                }]}


@dataclass(frozen=True)
class EngineMemory:
    """Explicit local root, no ambient MEMORY_ENGINE_ROOT and no mutations.

    Engine source must be importable separately. Technical lock files can be
    initialized by ContextualRecall. No HTTP endpoint is invented here.
    """
    root: str
    provider_id: str = "memory-engine/contextual-recall/0.1"

    def recall(self, query):
        root = Path(self.root).resolve(strict=True)
        persistent, history = root / "memory/persistent", root / "memory/history"
        if not persistent.is_dir() or not history.is_dir():
            raise ValueError("an existing isolated memory root is required")
        from core.backend.filesystem import FilesystemBackend
        from core.retrieval.contextual import ContextualRecall
        bundle = ContextualRecall(FilesystemBackend(persistent, history)).recall(
            query, mode="operational", max_items=5, max_chars=4000, max_item_chars=1000)
        # Preserve all fields, including future extension metadata and uncertainty.
        return snapshot(asdict(bundle))


@dataclass(frozen=True)
class BridgeMemory:
    """Opt-in remote memory port for Dialogue via SSH loopback forwarding.

    No ambient credentials, no direct filesystem access and no silent fallback.
    Dialogue._recall already validates context and degrades on recall failures.
    """
    token_file: str
    port: int = 18765
    timeout: float = 10.0
    provider_id: str = "memory-bridge/1"

    def recall(self, query):
        from .memory_bridge_client import recall as remote_recall
        token_path = Path(self.token_file).expanduser()
        if token_path.is_symlink() or not token_path.is_file():
            raise ValueError("invalid memory bridge credential path")
        import os
        import stat
        info = token_path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("memory bridge credential must be owner-only")
        token = token_path.read_text(encoding="ascii").strip()
        result = remote_recall(query, token=token, port=self.port, timeout=self.timeout)
        return snapshot(result)
