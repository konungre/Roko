"""Explicit live client-contract qualification; no GUI integration."""
import pathlib,sys,json,sqlite3,subprocess,os,time
import argparse
parser=argparse.ArgumentParser(description='Explicit real endpoint cancellation/recovery and deferred-stop commit race')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
config=parser.parse_args();root=config.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
code=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(code))
from cancellation_ux import CancellationUX
fixture=config.source_db.resolve()
with sqlite3.connect(fixture.as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(root/'history.sqlite') as b:a.backup(b)
with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as db:
 row=db.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone()
if row is None or row[0]!=6 or len(json.loads(row[1]))!=12 or len(json.loads(row[2]))!=2 or row[3] is not None:raise ValueError('Requires verified six-turn checkpoint with two observations and no pending claim')
env={**os.environ,'ROKO_FRESH_PROFILE':str(config.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
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

def inspect(u,endpoint):
 q=u.inspect(confirmed=True);response=endpoint.call(q['packet']);u.receive_snapshot(q['ticket'],response);return response
owner=Endpoint('owner');observer=Endpoint('observer');checks={};registry={};original=dict(api_version=2,op='turn',session_id='language',request_id='ux-stop',expected_revision=6,text='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4,context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)],max_output_tokens=128)
u=CancellationUX(original['text'])
try:
 for e in (owner,observer):assert e.call(dict(api_version=2,op='limits',session_id='language'))['input_token_limit']==768
 sent=u.begin(original,confirmed=True,owned_worker='owner-A');registry['owner-A']=u.worker_binding();u.edit('unsent text during stop');owner.send(sent)
 supervisor=None;resident=[];start=time.monotonic()
 while time.monotonic()-start<90:
  for line in (root/'owner-stderr.txt').read_text().splitlines():
   if line.startswith('ROKO_NATIVE_STARTED '):supervisor=json.loads(line.split(' ',1)[1])['supervisor_pid']
  resident=group(supervisor) if supervisor else []
  if any(r['rss']>3*1024**3 and r['cpu_ticks']>20 for r in resident):break
  if owner.p.poll() is not None:raise RuntimeError('Owner exited early')
  time.sleep(.03)
 checks['real_resident_inference']=any(r['rss']>3*1024**3 and r['cpu_ticks']>20 for r in resident)
 old=u.inspect(confirmed=True);old_snapshot=observer.call(old['packet']);stop=u.request_cancel(confirmed=True)
 checks['proposal_did_not_stop_worker']=owner.p.poll() is None
 checks['registry_binding_required']=not u.can_execute_cancel(stop,current_binding=dict(registry['owner-A'],request_id='other'))
 if not u.can_execute_cancel(stop,current_binding=registry['owner-A']):raise AssertionError('Owned stop refused')
 owner.p.terminate();owner.p.wait(timeout=10);owner.p.stdin.close();start=time.monotonic()
 while supervisor and group(supervisor) and time.monotonic()-start<10:time.sleep(.03)
 remaining=group(supervisor) if supervisor else [];checks['native_cleanup_observed']=not remaining
 u.worker_stopped(stop)
 try:u.receive_snapshot(old['ticket'],old_snapshot)
 except ValueError:checks['prestop_snapshot_fenced']=True
 else:checks['prestop_snapshot_fenced']=False
 pending=inspect(u,observer);checks['real_pending_claim_visible']=pending['pending']==original['request_id']
 recovery=u.recover(confirmed=True);recovery_ticket=u.recovery_ticket();recovery_reply=observer.call(recovery);u.receive_recovery_reply(recovery_reply,ticket=recovery_ticket)
 checks['actual_explicit_recovery']=recovery_reply['status']=='interrupted' and u.view()['request_outcome']=='interrupted_reported'
 after=inspect(u,observer);checks['recovery_kept_full_history']=after['history']==old_snapshot['history'] and after['revision']==6 and after['pending'] is None
 u.review_and_release(confirmed=True);checks['draft_preserved_after_stop']=u.view()['draft']=='unsent text during stop'
 # User explicitly chooses a new ID after reviewing interruption.
 u.edit(original['text']);retry=dict(original,request_id='ux-explicit-retry',max_output_tokens=32);sent=u.begin(retry,confirmed=True,owned_worker='observer-B');registry['observer-B']=u.worker_binding();observer.send(sent);u.edit('draft after retry')
 response=observer.get();u.receive_reply(response);first_view=u.view();snap=inspect(u,observer);u.review_and_release(confirmed=True)
 checks['new_id_real_reply']=response['status']=='completed' and response['revision']==7 and response['generation']['input_tokens']>512
 checks['existing_reply_panel_used']=first_view['reply_panel']['reply_revision']==7 and first_view['reply_panel']['live_host_state_established'] is False and first_view['reply_panel']['mutation_authority'] is False
 checks['draft_preserved_after_retry']=u.view()['draft']=='draft after retry'
 # Deliberately defer the local stop proposal until a real commit reply wins.
 text='Name both creatures.';u.edit(text);race=dict(api_version=2,op='turn',session_id='language',request_id='ux-commit-race',expected_revision=7,text=text,context=[],max_output_tokens=32)
 sent=u.begin(race,confirmed=True,owned_worker='observer-B');registry['observer-B']=u.worker_binding();observer.send(sent);queued=u.request_cancel(confirmed=True)
 checks['queued_stop_initially_valid']=u.can_execute_cancel(queued,current_binding=registry['observer-B']);u.edit('unsent text after commit race')
 committed=observer.get();u.receive_reply(committed)
 checks['real_commit_suppresses_queued_stop']=not u.can_execute_cancel(queued,current_binding=registry['observer-B']) and u.view()['request_outcome']=='committed_reply_received'
 u.cancel_not_executed(queued);final=inspect(u,observer);u.review_and_release(confirmed=True)
 checks['commit_never_labelled_cancelled']=committed['status']=='completed' and committed['revision']==8
 checks['full_sixteen_messages']=len(final['history'])==16 and final['history'][:14]==snap['history']
 checks['draft_preserved_after_commit_race']=u.view()['draft']=='unsent text after commit race'
 checks['stale_stop_not_executable']=not u.can_execute_cancel(queued,current_binding=dict(registry['observer-B'],request_id='later-work'))
 checks['worker_remains_usable']=observer.call(dict(api_version=2,op='limits',session_id='language'))['revision']==8
 observer.close();owner.close()
 receipt=next(json.loads(x.split(' ',1)[1]) for x in (root/'observer-stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '));checks['exact_two_native_completions']=len(receipt['native_calls'])==2 and all(x['returncode']==0 for x in receipt['native_calls'])
 result=dict(passed=all(checks.values()),checks=checks,resident_before=resident,native_after=remaining,replies=dict(retry=response,commit_race=committed),provenance='Real endpoint stop/recover plus deterministically deferred-stop commit race on current cloud host. Uses actual latest-main DesktopReplyPanel. No graphical integration or production activation.')
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
finally:
 for e in (owner,observer):
  if e.p.poll() is None:e.p.terminate();e.p.wait(timeout=10)
