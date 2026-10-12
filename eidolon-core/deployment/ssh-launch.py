# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : ssh-launch.py
# Description : Lanceur isole du collecteur SSH installe par root
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eidolon_core.darme_ssh import main
main()
