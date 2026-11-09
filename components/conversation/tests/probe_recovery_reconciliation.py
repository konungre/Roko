"""Explicit seeded-claim endpoint test; no native model generation or GUI."""
import pathlib,sys,json,sqlite3,subprocess,os,time
import argparse
parser=argparse.ArgumentParser(description='Real recovery controls with deliberately withheld operation results; zero model inference')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
config=parser.parse_args();root=config.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
code=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(code))
from cancellation_ux import CancellationUX
fixture=config.source_db.resolve()
with sqlite3.connect(fixture.as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(root/'history.sqlite') as b:a.backup(b)
env={**os.environ,'ROKO_FRESH_PROFILE':str(config.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
seed="import sys;sys.path.insert(0,sys.argv[1]);from durable_store import Store;s=Store(sys.argv[2]);[s.start(x,'recover-me',0,dict(text='Preserve my draft',context=[],max_output_tokens=32)) for x in ('pending-case','done-case')];s.close()"
child=subprocess.run([sys.executable,'-B','-c',seed,str(code),str(root/'history.sqlite')],env=env,check=True)
class Endpoint:
 def __init__(self,name):
  self.name=name;self.index=0;self.requests=[];self.out=(root/(name+'-stdout.txt')).open('wb');self.err=(root/(name+'-stderr.txt')).open('wb');self.p=subprocess.Popen([sys.executable,'-B',str(code/'durable_server.py')],stdin=subprocess.PIPE,stdout=self.out,stderr=self.err,env=env)
 def send(self,packet):
  self.requests.append(packet);(root/(self.name+'-requests.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in self.requests));self.p.stdin.write((json.dumps(packet)+'\n').encode());self.p.stdin.flush()
 def get(self):
  start=time.monotonic()
  while time.monotonic()-start<180:
   rows=(root/(self.name+'-stdout.txt')).read_text().splitlines()
   if len(rows)>self.index:self.index+=1;return json.loads(rows[self.index-1])
   if self.p.poll() is not None:raise RuntimeError('Endpoint exited '+self.name)
   time.sleep(.03)
  raise RuntimeError('Response deadline')
 def call(self,packet):self.send(packet);return self.get()
 def close(self):
  if self.p.poll() is None:self.p.stdin.close();self.p.wait(timeout=30)
  self.out.close();self.err.close()
def group(pid):
 rows=[]
 for path in pathlib.Path('/proc').glob('[0-9]*/stat'):
  try:
   f=path.read_text().rsplit(')',1)[1].split()
   if int(f[2])!=pid or f[0]=='Z':continue
   status=(path.parent/'status').read_text();rss=next((int(x.split()[1])*1024 for x in status.splitlines() if x.startswith('VmRSS:')),0);rows.append(dict(pid=int(path.parent.name),start=f[19],rss=rss,cpu_ticks=int(f[11])+int(f[12]),comm=(path.parent/'comm').read_text().strip()))
  except (OSError,ValueError):pass
 return rows



def request(session):return dict(api_version=2,op='turn',session_id=session,request_id='recover-me',expected_revision=0,text='Preserve my draft',context=[],max_output_tokens=32)
def inspect(u):
 q=u.inspect(confirmed=True);snap=endpoint.call(q['packet']);u.receive_snapshot(q['ticket'],snap);return snap
def prepare(session):
 u=CancellationUX('Preserve my draft');u.begin(request(session),confirmed=True,owned_worker='seeded-owned-worker');u.edit('next unsent draft '+session);p=u.request_cancel(confirmed=True);u.worker_stopped(p);inspect(u);return u
endpoint=Endpoint('controls');checks={}
try:
 endpoint.call(dict(api_version=2,op='limits',session_id='language'))
 u=prepare('pending-case');first=u.recover(confirmed=True);old=u.recovery_ticket();u.transport_lost()
 # The first recovery proposal was lost before dispatch: backend still pending.
 pending=inspect(u);checks['backend_pending_remains']=pending['pending']=='recover-me'
 try:u.review_and_release(confirmed=True)
 except ValueError:checks['uncertain_operation_blocks_early_release']=True
 else:checks['uncertain_operation_blocks_early_release']=False
 try:u.reconcile_recovery()
 except ValueError:checks['reconciliation_requires_confirmation']=True
 else:checks['reconciliation_requires_confirmation']=False
 checks['explicit_pending_reconciliation']=u.reconcile_recovery(confirmed=True)['resolution']=='pending_claim'
 retry=u.recover(confirmed=True);new=u.recovery_ticket();checks['new_operation_ticket']=new!=old and retry==first
 actual=endpoint.call(retry)
 try:u.receive_recovery_reply(actual,ticket=old)
 except ValueError:checks['old_callback_cannot_settle_retry']=True
 else:checks['old_callback_cannot_settle_retry']=False
 u.receive_recovery_reply(actual,ticket=new);inspect(u);u.review_and_release(confirmed=True);checks['pending_path_released_draft']=u.view()['draft']=='next unsent draft pending-case'
 v=prepare('done-case');operation=v.recover(confirmed=True);late=v.recovery_ticket();withheld=endpoint.call(operation);checks['backend_recovery_succeeded']=withheld['status']=='interrupted';v.transport_lost()
 clear=inspect(v);checks['snapshot_no_pending_after_success']=clear['pending'] is None and clear['revision']==0
 checks['explicit_no_pending_reconciliation']=v.reconcile_recovery(confirmed=True)['resolution']=='no_pending_claim';checks['no_false_terminal_receipt_claim']=v.view()['request_outcome']!='interrupted_reported'
 try:v.receive_recovery_reply(withheld,ticket=late)
 except ValueError:checks['late_retired_callback_rejected']=True
 else:checks['late_retired_callback_rejected']=False
 v.review_and_release(confirmed=True);checks['completed_path_released_draft']=v.view()['draft']=='next unsent draft done-case'
 endpoint.close();receipt=next(json.loads(x.split(' ',1)[1]) for x in (root/'controls-stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '));checks['zero_native_work']=all(receipt[k]==[] for k in ('native_calls','mork_receipts','cognitive_receipts','ecan_receipts','token_counter_calls'))
 with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  original=db.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone();states=list(db.execute("select session_id,status from requests where request_id='recover-me'"))
 checks['original_history_and_ledger_untouched']=original[0]==6 and len(json.loads(original[1]))==12 and len(json.loads(original[2]))==2 and original[3] is None
 checks['both_seeded_claims_terminal']=states==[('pending-case','interrupted'),('done-case','interrupted')]
 result=dict(passed=all(checks.values()),checks=checks,provenance='Actual JSON-lines recovery/snapshot endpoint with two real seeded dead-owner Store claims. UI operation callbacks deliberately withheld; no new model inference. Not GUI or network-fault simulation.')
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
finally:
 if endpoint.p.poll() is None:endpoint.p.terminate();endpoint.p.wait(timeout=10)
