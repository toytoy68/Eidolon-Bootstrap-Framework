# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_driver.py
# Description : Parent sacrifiable pour le test d'exécutant orphelin
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Only synthetic marker files, inside the test's temporary directory."""
from dataclasses import replace
import sys

from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Registry, default_registry
from tests.support import marker_tool


if __name__ == "__main__":
    registry = Registry([replace(default_registry().get("text.stats"), execute=marker_tool)])
    Runtime(Store(sys.argv[1]), registry=registry).run(sys.argv[2])
