# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_c122_media_links.py
# Description : Contre-revue des identités média et du digest de sauvegarde v4
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import tempfile
from eidolon_core import conversation_media as cm
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.conversation_storage import inspect as inspect_storage
from eidolon_core.conversation_media_results import link_job, views_for
from eidolon_core.media_agents import prepare, write_record
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.store import Store

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder); conv = ConversationStore(Store(root / 'state'), create=True)
    cid = conv.open(client_id='fixture', client_key='open')['conversation_id']
    turn = conv.append_turn(cid, client_id='fixture', client_turn_key='one', text='Un phare')['turn']
    _, proposal = cm.propose(conv, turn, {'template': 'media.image.create', 'parameters': {
        'prompt': 'Un phare', 'format': 'square'}}, owner_client_id='fixture')
    artifacts = root / 'artifacts'; initialize(artifacts)
    job_dir = root / 'job'; job_dir.mkdir(mode=0o700)
    job = {'schema': 'media-job/1', 'id': 'media-' + '1' * 32, 'state': 'QUEUED',
           'request': prepare(cm.media_request(proposal)), 'automatic_retry': False}
    write_record(job_dir, job)
    before = inspect_storage(conv.path)
    link_job(conv, owner_client_id='fixture', conversation_id=cid, proposal=proposal,
             job_dir=str(job_dir), artifact_root=str(artifacts))
    after = inspect_storage(conv.path)
    assert len(conv.media_links(owner_client_id='fixture', conversation_id=cid)) == 1
    assert before['logical_sha256'] == after['logical_sha256']
    assert 'media_links' not in after['rows']
    first = views_for(conv, owner_client_id='fixture', conversation_id=cid)[0]
    job['id'] = 'media-' + '2' * 32
    job['state'] = 'RESULT_UNVERIFIED'
    job['result'] = {'state': 'RESULT_UNVERIFIED', 'text': 'Observation d’un autre travail synthétique'}
    write_record(job_dir, job)
    replaced = views_for(conv, owner_client_id='fixture', conversation_id=cid)[0]
    assert first['job_id'] != replaced['job_id']
    assert replaced['binding'] == 'MATCHED'
    assert replaced['observation']['text'] == job['result']['text']
    print(json.dumps({'status': 'FINDINGS_REPRODUCED', 'source': 'C122/0a3a2e5',
          'G123-R1': {'same_request_different_job_accepted': True, 'foreign_observation_shown': True},
          'G099-R1': {'media_links_missing_from_logical_digest': True, 'digest_unchanged_after_link': True,
                      'physical_backup_loss_claimed': False}, 'real_engine': False}, indent=2))
