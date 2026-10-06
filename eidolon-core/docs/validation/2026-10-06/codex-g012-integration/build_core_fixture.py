# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : build_core_fixture.py
# Description : Capture Core synthétique hors catalogue pour revue G012
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import tempfile

from eidolon_core.client_sync import ClientSync
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

with tempfile.TemporaryDirectory(prefix="eidolon-g012-review-") as directory:
    store = Store(directory)
    runtime = Runtime(store)
    mission = runtime.create("unsupported synthetic request")
    runtime.run(mission["id"])
    print(json.dumps(ClientSync(store).snapshot(mission["id"]), indent=2))
