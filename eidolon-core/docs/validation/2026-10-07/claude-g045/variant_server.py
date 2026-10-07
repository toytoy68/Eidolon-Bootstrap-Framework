# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : variant_server.py
# Description : Lance ReadServer tel quel ou avec une variante de libération de place (C-TASK-G045)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 variant_server.py <state> <token-file> original|release-first
Measurement helper only: the variant is a PROPOSAL, not a change of http_api.py."""
import sys

from eidolon_core.http_api import ReadServer, read_token


class ReleaseFirst(ReadServer):
    """Same as ReadServer, but the slot is freed BEFORE the socket is closed."""
    def _serve_connection(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            with self._worker_lock:
                self._workers.pop(request, None)
            self.shutdown_request(request)


state, token_file, variant = sys.argv[1:4]
cls = ReleaseFirst if variant == "release-first" else ReadServer
with cls(state, read_token(token_file), port=0) as server:
    print(f"PORT {server.server_port}", flush=True)
    server.serve_forever()
