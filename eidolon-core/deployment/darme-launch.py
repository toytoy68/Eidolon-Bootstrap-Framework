# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : launch.py
# Description : Lanceur isole du paquet DARME installe par root
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eidolon_core.darme_service import main
main()
