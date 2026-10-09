# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_i6_migration.py
# Description : Après une initialisation coupée avant la liaison (I6), la migration explicite rétablit-elle l'ouverture ? (G093)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probe_i6_migration.py <frozen eidolon-core/src>  — temporary folders, synthetic fixture only."""
import os, subprocess, sys, tempfile
from pathlib import Path
SRC = str(Path(sys.argv[1]).resolve()); sys.path.insert(0, SRC); sys.dont_write_bytecode = True
from eidolon_core.research_runtime import ResearchRuntime, migrate_research_pauses  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

CRASH = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core import research_runtime as rr
from eidolon_core.store import Store
real = rr.SyntheticResearchBackend.__init__
def init(self, *a, **k):
    real(self, *a, **k); os._exit(9)
rr.SyntheticResearchBackend.__init__ = init
rr.ResearchRuntime(Store(sys.argv[2]))
"""

def attempt(label, fn):
    try:
        r = fn(); print(f"{label} : {r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label} : {type(exc).__name__} {getattr(exc, 'code', None) or exc}")

def main():
    # The research tool runs in a "spawn" worker that re-imports this file: keep effects under main.
    with tempfile.TemporaryDirectory() as tmp:
        s = Path(tmp) / "state"
        p = subprocess.run([sys.executable, "-c", CRASH, SRC, str(s)], env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        print(f"arrêt before_binding_commit : code {p.returncode}")
        attempt("1 réouverture sans migration", lambda: ResearchRuntime(Store(s)).backend.guard_id[:2] + "…")
        attempt("2 migration sans motif", lambda: migrate_research_pauses(Store(s), actor="toytoy", reason=""))
        attempt("3 migration explicite", lambda: {k: v for k, v in migrate_research_pauses(
            Store(s), actor="opérateur synthétique", reason="initialisation coupée, revue G093").items() if k not in ("database_id", "guard_id")})
        attempt("4 réouverture après migration", lambda: "construite" if ResearchRuntime(Store(s)).backend.pause_id else "?")
        attempt("5 seconde migration", lambda: migrate_research_pauses(Store(s), actor="opérateur synthétique", reason="rejeu"))
        rt = ResearchRuntime(Store(s))
        attempt("6 mission synthétique après migration", lambda: rt.run(rt.create_research("notice synthetique", required_pages=1)["id"])["status"])


if __name__ == "__main__":
    main()
