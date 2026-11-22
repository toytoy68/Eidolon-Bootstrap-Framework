from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import tempfile,runpy,io,json,os,time,contextlib
script=Path(__file__).with_name('nas-health.py');results=[]
for power,icmp,age,expected in [(2,False,2000,'OFF_BY_SHELLY'),(100,False,2000,'POWERED_BUT_UNREACHABLE'),(100,True,0,'POWERED_AND_REACHABLE'),(None,True,0,'POWER_UNKNOWN')]:
 with tempfile.TemporaryDirectory() as d:
  home=Path(d);f=home/'archive/network/latest-summary.json';f.parent.mkdir(parents=True);f.write_text('{}');os.utime(f,(time.time()-age,time.time()-age))
  def run(args,**kwargs):return SimpleNamespace(returncode=0 if args[0].endswith('zfs') or icmp else 1,stdout='')
  class Opener:
   def open(self,*a,**kw):
    if power is None:raise OSError('unavailable')
    return io.BytesIO(json.dumps({'apower':power}).encode())
  with patch.object(Path,'home',return_value=home),patch('subprocess.run',side_effect=run),patch('urllib.request.build_opener',return_value=Opener()),contextlib.redirect_stdout(io.StringIO()):
   r=runpy.run_path(str(script));r['lock'].close()
   assert r['out']['x399_state']==expected
   if power==2:assert r['out']['archive_state']=='PAUSED_HOST_OFF'
   if not icmp:
    r=runpy.run_path(str(script));r['lock'].close();assert r['out']['switch_state']=='UNREACHABLE_PENDING'
    r=runpy.run_path(str(script));r['lock'].close();assert r['out']['switch_state']=='UNREACHABLE_CONFIRMED'
  results.append(dict(expected=expected,passed=True))
Path(__file__).with_name('monitor-tests.json').write_text(json.dumps(dict(passed=True,scenarios=results,simulated=True,external_network=False),indent=2));print(json.dumps(results))
