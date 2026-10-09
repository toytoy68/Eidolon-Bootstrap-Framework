# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : crash_g126.py
# Description : Processus tué pendant l'appel moteur simulé, après admission et réservation (C-TASK-G126)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""crash_g126.py <state> <worker root> <worker id> <store id> <ticket> <config json> — exits 77 inside the engine."""
import json
import os
import sys

from eidolon_core.conversation_store import ConversationStore
from eidolon_core.media_worker import MediaWorker
from eidolon_core.store import Store

state, root, worker_id, store_id, ticket, config = sys.argv[1:7]


class Dying:
    def plan(self, *args):
        return {"adapter": "claude-g126-crash"}

    def run(self, request, *args, progress):
        progress("QUEUE_SUBMITTING", {})
        os._exit(77)                         # the engine may or may not have received the job


MediaWorker(root, worker_id=worker_id, store_id=store_id).run_once(
    ticket, client_id="pc", conversations=ConversationStore(Store(state)), config=json.loads(config),
    execute_local=True, backend=Dying())
