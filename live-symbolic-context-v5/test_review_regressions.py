import sys,json,hashlib,tempfile,time,stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'source'),str(ROOT/'capsule-bridge'),str(ROOT.parent/'omega-baseline/adapters')]
import live_context,gateway
from ecan_guest_contract import make_request

# Metadata doubles isolate the directory validation branch without root writes.
with tempfile.TemporaryDirectory() as d:
 capsule=Path(d)/'capsule';bridge=capsule/'bridge';bridge.mkdir(parents=True);f=bridge/'fixture.py';f.write_text('inert source\n')
 data={'tree_entries':{str(bridge):['fixture.py']},'files':{str(f):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}}}
 raw=json.dumps(data).encode();(capsule/'inputs.json').write_bytes(raw);pin=hashlib.sha256(raw).hexdigest()
 real=Path.lstat
 def metadata(p):
  i=real(p)
  return SimpleNamespace(st_mode=(stat.S_IFDIR|(0o777 if p==bridge else 0o755)) if stat.S_ISDIR(i.st_mode) else stat.S_IFREG|0o444,st_uid=0,st_size=i.st_size)
 with patch.object(live_context,'CAPSULE',capsule),patch.object(Path,'lstat',metadata):
  try:live_context._preflight(pin,time.monotonic()+10);dir_rejected=False
  except ValueError as e:dir_rejected=True;print('directory rejection',str(e))
 assert dir_rejected, 'Writable nested capsule directory was accepted'
 print('writable_nested_directory_rejected',dir_rejected)

class Cancelled(BaseException):pass
class Stream:
 def __init__(self):self.closed=False
 def fileno(self):return 10
 def close(self):self.closed=True
class Process:
 pid=1234;returncode=None
 def __init__(self):self.stdin=Stream();self.stdout=Stream();self.stderr=Stream()
class Selector:
 def register(self,*a):pass
 def get_map(self):return {}
 def close(self):pass
process=Process()
def stopped(p,deadline):p.returncode=0;return {'reaped':True,'returncode':0,'signaled':True,'ownership':'owned-through-final-signal'}
request=make_request(task_id='review',revision=1,snapshot_sha256='a'*64,candidates=[{'id':'c00','sti':1,'lti':0,'stimulus':0}],focus_capacity=1,selection_count=1)
with tempfile.TemporaryDirectory() as d,patch.object(gateway,'WORK',Path(d)),patch.object(gateway,'verify_inputs',side_effect=[{},Cancelled('cancel during posthash')]),patch.object(gateway,'checked_free',return_value={'test_double_only':True}),patch.object(gateway,'available',return_value=8*1024**3),patch.object(gateway.subprocess,'Popen',return_value=process),patch.object(gateway.selectors,'DefaultSelector',return_value=Selector()),patch.object(gateway.os,'set_blocking'),patch.object(gateway,'observed_exit',return_value=object()),patch.object(gateway,'stop_owned',side_effect=stopped),patch.object(gateway,'group_empty',return_value=True),patch.object(gateway.signal,'signal'),patch.object(gateway,'validate_completed',return_value=({},{})):
 try:gateway.run_native('ecan',request,'a'*64,outer_deadline=time.monotonic()+60)
 except Cancelled as e:
  print('posthash_cancellation_class_preserved',True)
  assert hasattr(e,'receipt'), 'Completed native child receipt lost on cancellation'
  assert e.receipt['cleanup']['reaped'] and e.receipt['group_empty']
  print('posthash_cancellation_has_current_receipt',hasattr(e,'receipt'))
 else:raise AssertionError('Original cancellation class did not escape')
