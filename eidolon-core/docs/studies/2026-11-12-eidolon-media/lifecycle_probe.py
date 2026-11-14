# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : lifecycle_probe.py
# Description : Sonde réelle de progression, idempotence et annulation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error
import uuid

root=Path(sys.argv[1]);token=(root/'token').read_text().strip()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def api(path,data=None,key=None,extra=None):
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    headers.update(extra or {})
    req=urllib.request.Request('http://127.0.0.1:8190'+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    with opener.open(req,timeout=10) as r:return json.load(r)
report={}
for key,headers in [('unauthorized',{'Authorization':'wrong'}),('browser_origin',{'Origin':'https://example.com'})]:
    try:api('/health',extra=headers);raise AssertionError('unauthorized access accepted')
    except urllib.error.HTTPError as e:report[key]=e.code;assert e.code==401
request={'profile':'sd15-text','checkpoint':'sd15-base','prompt':'A green forest beside a lake, painting',
         'width':768,'height':768,'steps':40,'seed':791}
key='cancel-'+uuid.uuid4().hex
first=api('/v1/jobs',request,key)
assert api('/v1/jobs',request,key)['id']==first['id'];report['idempotency_same_id']=True
deadline=time.monotonic()+60
while time.monotonic()<deadline:
    j=api('/v1/jobs/'+first['id'])
    if j.get('progress',{}).get('value',0)>=2:break
    assert j['state'] not in ['SUCCEEDED','FAILED','REVIEW_REQUIRED','CANCELLED'],j
    time.sleep(0.1)
else:raise AssertionError('no observed sampling progress')
report['progress_before_cancel']=j['progress']
waiting=api('/v1/jobs',request,'waiting-'+uuid.uuid4().hex)
cancelled=api('/v1/jobs/'+waiting['id']+'/cancel',{})
assert cancelled['state']=='CANCELLED';report['waiting_cancel']=cancelled
requested=api('/v1/jobs/'+first['id']+'/cancel',{})
report['running_cancel_request']=requested['state'];assert requested['state']=='CANCEL_REQUESTED'
deadline=time.monotonic()+30
while time.monotonic()<deadline:
    j=api('/v1/jobs/'+first['id'])
    if j['state']=='CANCELLED':break
    assert j['state'] not in ['SUCCEEDED','FAILED','REVIEW_REQUIRED'],j
    time.sleep(0.2)
else:raise AssertionError('no engine interruption evidence')
report['running_cancel_confirmed']=j
(root/'lifecycle-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
