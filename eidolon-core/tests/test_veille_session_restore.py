# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_veille_session_restore.py
# Description : Revalidate ownership and credentials after signed conversation restore
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Hermes-inspired scenarios on Eidolon's real API and signed SQLite restore.

Synthetic clients only. This is not a webhook transport or physical reboot test.
"""
import json
import shutil

import pytest

from eidolon_core import backup_signature, conversation_storage
from eidolon_core.beta_runtime import BetaRuntime
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_api import ConversationAPI, PREFIX
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
from tests.test_beta_runtime_g270 import config


class Lab:
    def __init__(self, root):
        self.root = root
        self.runtime = synthetic_runtime(Store(root / 'core'))
        conversations = ConversationStore(self.runtime.store, create=True)
        self.credentials = ClientCredentials(self.runtime.store, create=True)
        self.clients = [self.credentials.pair(client_id=f'pc{i}', actor=f'actor{i}') for i in range(2)]
        self.config = config(root)
        self.api = None
        self.start()
        self.ids = []
        for i in range(2):
            status, value = self.post(i, 'open', {'client_key': 'same-key'})
            assert status == 200
            self.ids.append(value['conversation_id'])
            assert self.turn(i)[0] == 200
        self.backup = root / 'signed.sqlite3'
        conversation_storage.backup(conversations.path, self.backup)
        self.signer = conversations.directory / backup_signature.SERVER_PUBLIC_KEY

    def start(self):
        self.api = ConversationAPI(self.runtime,
            dialogue_model=SimulatedDialogueModel(self.runtime.catalog),
            services=BetaRuntime(self.config))

    def close(self):
        if self.api is not None:
            self.api.close()
            self.api = None

    def restore(self):
        self.close()
        result = conversation_storage.restore_backup(self.runtime.store, self.backup, signer=self.signer)
        assert result['status'] == 'RESTORED' and result['signature'] == 'VERIFIED'
        self.start()

    def post(self, client, route, data, token=None):
        return self.api.handle('POST', PREFIX + route,
            {'Authorization': ['Bearer ' + (token or self.clients[client]['token'])],
             'Content-Type': ['application/json']}, json.dumps(data).encode())

    def turn(self, client):
        return self.post(client, 'turn', {'conversation_id': self.ids[client],
            'client_turn_key': 'same-turn-key', 'text': f'Bonjour marqueur-profil-{client}'})


@pytest.fixture
def lab(tmp_path):
    if shutil.which('openssl') is None:
        pytest.skip('OpenSSL is required for a real signed backup')
    item = Lab(tmp_path)
    try:
        yield item
    finally:
        item.close()


def test_signed_restore_keeps_owners_and_replays_only_their_own_turn(lab):
    assert lab.ids[0] != lab.ids[1]
    lab.restore()
    for i in range(2):
        status, value = lab.turn(i)
        assert status == 200 and value['replayed'] and not value['model_called']
        status, page = lab.post(i, 'page', {'conversation_id': lab.ids[i]})
        assert status == 200 and len(page['items']) == 1
        assert f'marqueur-profil-{1-i}' not in json.dumps(page)
        for route, body in [
            ('page', {'conversation_id': lab.ids[1-i]}),
            ('turn', {'conversation_id': lab.ids[1-i], 'client_turn_key': 'steal', 'text': 'Bonjour'}),
        ]:
            status, value = lab.post(i, route, body)
            assert status == 404 and value['error'] == 'CONVERSATION_UNKNOWN'
        status, session = lab.post(i, 'session_status', {})
        assert status == 200 and session['profile_id'] == f'user{i}'


def test_conversation_restore_does_not_resurrect_a_revoked_credential(lab):
    lab.credentials.revoke('pc0')  # Revoked after the snapshot; clients DB is independent.
    lab.restore()
    assert lab.post(0, 'page', {'conversation_id': lab.ids[0]})[0] == 401
    assert lab.post(1, 'page', {'conversation_id': lab.ids[1]})[0] == 200


def test_conversation_restore_keeps_key_rotation_and_rejects_old_token(lab):
    rotated = lab.credentials.rotate('pc0')
    lab.restore()
    assert lab.post(0, 'page', {'conversation_id': lab.ids[0]})[0] == 401
    assert lab.post(0, 'page', {'conversation_id': lab.ids[0]}, token=rotated['token'])[0] == 200
    assert lab.post(0, 'page', {'conversation_id': lab.ids[1]}, token=rotated['token'])[0] == 404


def test_restart_never_falls_back_when_an_operator_binding_changes(lab):
    lab.close()
    lab.config['clients']['pc0'] = 'user1'
    with pytest.raises(ValueError, match='bindings changed'):
        BetaRuntime(lab.config)
