# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g087_credentials.py
# Description : Contre-revue indépendante des identités d'appairage, données synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import shutil
import tempfile
from eidolon_core.client_credentials import ClientCredentials, CredentialError
from eidolon_core.store import Store

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    a = ClientCredentials(Store(root/'a'), create=True)
    b = ClientCredentials(Store(root/'b'), create=True)
    client = b.pair(client_id='fixture', actor='synthetic other Store')
    a.path.unlink()
    shutil.copyfile(b.path, a.path)
    a.path.chmod(0o600)
    accepted = a.authenticate(client['token'])
    assert accepted == {'client_id': 'fixture', 'actor': 'synthetic other Store'}
    reopened = ClientCredentials(Store(root/'a')).authenticate(client['token'])
    assert reopened == accepted
    other = root/'other'; other.mkdir(mode=0o700)
    s = Store(root/'linked')
    (s.directory/'conversations').symlink_to(other, target_is_directory=True)
    try:
        ClientCredentials(s, create=True)
    except CredentialError:
        pass
    else:
        raise AssertionError('linked parent accepted')
    assert (other/'clients.sqlite3').exists()
    assert (other/'clients.sqlite3').stat().st_size == 0
    print(json.dumps({'status':'FINDINGS_REPRODUCED', 'source':'C107/b654a3b',
        'G087-R1': 'credentials copied from another Store accepted by existing and reopened instances',
        'G087-R2': 'linked conversation directory refused after creating empty external clients.sqlite3',
        'synthetic_only': True, 'tokens_in_output': False}, indent=2))
