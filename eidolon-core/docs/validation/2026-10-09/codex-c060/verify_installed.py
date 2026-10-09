# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : verify_installed.py
# Description : Couverture des analyses, inspection CLI installée de journaux synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import eidolon_core.media_status as status

core=Path(__file__).resolve().parents[4]
installed=Path(status.__file__).parent
sources=sorted((core/'src/eidolon_core').glob('*.py'))
assert installed != core/'src/eidolon_core'
assert all((installed/p.name).read_bytes()==p.read_bytes() for p in sources)
env=dict(os.environ);env.pop('PYTHONPATH',None)
reports=[]
with tempfile.TemporaryDirectory(prefix='eidolon-c060-') as folder:
    for agent,frames in [('video',8),('image',1),('video',True)]:
        job=Path(folder)/str(len(reports));job.mkdir(mode=0o700)
        coverage='single_image' if agent=='image' else 'first_40s_up_to_8_frames_no_audio'
        value={'schema':'media-job/1','id':'media-'+'a'*32,'agent':agent,'operation':'analyze',
               'state':'RESULT_UNVERIFIED','automatic_retry':False,
               'request':{'source':'missing-source','prompt':'PRIVATE_PROMPT'},
               'backend':{'adapter':'ollama-vision/1','coverage':coverage},
               'result':{'state':'RESULT_UNVERIFIED','coverage':coverage,'frames_analyzed':frames,
                         'audio_analyzed':False,'text':'PRIVATE_MODEL\u001b[2J'}}
        journal=job/'job.json';journal.write_text(json.dumps(value));before=journal.read_bytes()
        command=[str(Path(sys.executable).parent/'eidolon-media'),'inspect','--job',str(job)]
        human=subprocess.run(command+['--format','human'],cwd=folder,env=env,capture_output=True,text=True,timeout=5)
        machine=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True,timeout=5)
        assert human.returncode==machine.returncode==0 and human.stderr==machine.stderr==''
        assert json.loads(machine.stdout)==value and journal.read_bytes()==before
        assert 'PRIVATE' not in human.stdout and '\u001b' not in human.stdout and '[OK]' not in human.stdout
        if type(frames) is bool:
            assert 'Couverture absente, non reconnue ou incohérente' in human.stdout
            assert '40 premières secondes' not in human.stdout
        elif agent=='video':
            assert '40 premières secondes' in human.stdout and 'selon le journal : 8' in human.stdout
            assert 'Audio non analysé' in human.stdout
        else:
            assert 'Une image fournie au modèle' in human.stdout and '40 premières secondes' not in human.stdout
        reports.append({'agent':agent,'frames_field':frames,'json_unchanged':True,'human_scope_checked':True})
print(json.dumps({'status':'PASS','installed_modules_identical':len(sources),'synthetic_journals_only':True,
                  'engine_or_source_required':False,'checks':reports},indent=2))
