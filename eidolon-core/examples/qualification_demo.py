# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : qualification_demo.py
# Description : Démonstration hors CLI du validateur de rapports de qualification
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Validate the synthetic fixtures. No GPU, engine, model or network involved.

From eidolon-core/:  PYTHONPATH=src:. python -m examples.qualification_demo
"""
import json
from pathlib import Path
import sys

from eidolon_core.qualification import ReportError, validate

FIXTURES = Path(__file__).resolve().parent / "qualification"


def main(paths):
    verdicts = {}
    for path in paths or sorted(FIXTURES.glob("*.json")):
        path = Path(path)
        try:
            verdicts[path.name] = validate(path.read_bytes()).to_dict()
        except ReportError as exc:
            verdicts[path.name] = {"status": "MALFORMED", "error": str(exc)}
    print(json.dumps(verdicts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
