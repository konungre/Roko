"""Explicit native console test; source checkpoint stays read-only."""
import pathlib,sys,json,sqlite3,subprocess,os,time
import argparse
parser=argparse.ArgumentParser(description='Explicit real endpoint console qualification; no graphical integration')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
config=parser.parse_args();root=config.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
code=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(code))
from console_harness import ConsoleHarness
with sqlite3.connect(config.source_db.resolve().as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(root/'history.sqlite') as b:a.backup(b)
with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as db:
 row=db.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone()
if row is None or row[0]!=6 or len(json.loads(row[1]))!=12 or len(json.loads(row[2]))!=2 or row[3] is not None:raise ValueError('Unexpected qualified source checkpoint')
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



frames=[]
def show(label,h,started):frames.append(dict(label=label,text=h.render()))
def dispatch_snapshot(h,endpoint):
 assert h.action('inspect',confirmed=True);event=h.wire[-1];packet=endpoint.call(event['packet']);assert h.snapshot(event['ticket'],packet);return event,packet
owner=Endpoint('owner');observer=Endpoint('observer');checks={};h=ConsoleHarness('');started=time.monotonic()
try:
 for endpoint in (owner,observer):assert endpoint.call(dict(api_version=2,op='limits',session_id='language'))['input_token_limit']==768
 text='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4
 request=dict(api_version=2,op='turn',session_id='language',request_id='console-live-stop',expected_revision=6,text=text,context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)],max_output_tokens=128)
 h.edit(text);assert h.action('send',confirmed=True,request=request,owned_worker='owner-A');owner.send(h.wire[-1]['packet']);h.edit('My next unsent thought.');started=time.monotonic();show('After explicit Send; draft edited separately',h,started)
 start=time.monotonic();supervisor=None;resident=[]
 while time.monotonic()-start<90:
  for line in (root/'owner-stderr.txt').read_text().splitlines():
   if line.startswith('ROKO_NATIVE_STARTED '):supervisor=json.loads(line.split(' ',1)[1])['supervisor_pid']
  resident=group(supervisor) if supervisor else []
  if any(r['rss']>3*1024**3 and r['cpu_ticks']>20 for r in resident):break
  if owner.p.poll() is not None:raise RuntimeError('Owner exited before live stop')
  time.sleep(.03)
 checks['actual_resident_inference']=any(r['rss']>3*1024**3 and r['cpu_ticks']>20 for r in resident)
 before=(len(h.wire),len(h.stops));show('Waiting redraw; no action dispatched',h,started);checks['redraw_has_no_effect']=before==(len(h.wire),len(h.stops))
 assert h.action('stop',confirmed=True);stop=h.stops[-1];show('Explicit Stop proposal before execution',h,started);checks['proposal_is_not_execution']=owner.p.poll() is None
 assert h.ui.can_execute_cancel(stop,current_binding=h.registry['owner-A']);owner.p.terminate();owner.p.wait(timeout=10);owner.p.stdin.close();start=time.monotonic()
 while supervisor and group(supervisor) and time.monotonic()-start<10:time.sleep(.03)
 checks['cleanup_observed']=not group(supervisor);assert h.stopped(stop)
 old_event,old_snapshot=dispatch_snapshot(h,observer);checks['real_snapshot_pending']=old_snapshot['pending']==request['request_id'] and len(old_snapshot['history'])==12;show('Fresh actual snapshot after owned worker stop',h,started)
 assert h.action('recover',confirmed=True);recovery=h.wire[-1];withheld=observer.call(recovery['packet']);checks['actual_recovery_succeeded']=withheld['status']=='interrupted'
 # Deliberately withhold the control reply from the presentation, then report loss.
 h.loss();show('Recovery response withheld from presentation',h,started);wire_count=len(h.wire)
 checks['early_reconcile_blocked']=not h.action('reconcile',confirmed=True);checks['blocked_action_has_no_request']=len(h.wire)==wire_count;show('Readable blocked reconciliation',h,started)
 _,cleared=dispatch_snapshot(h,observer);assert h.action('reconcile',confirmed=True);checks['reconciled_no_pending']=h.decisions[-1]['resolution']=='no_pending_claim' and cleared['pending'] is None
 state_before=h.ui.view();wire_count=len(h.wire);checks['late_control_callback_ignored']=not h.recovery_reply(withheld,recovery['ticket']) and h.ui.view()==state_before and len(h.wire)==wire_count;show('Late recovery callback ignored without traceback',h,started)
 assert h.action('release',confirmed=True);checks['draft_preserved_after_recovery']=h.ui.view()['draft']=='My next unsent thought.';checks['history_still_visible_after_release']='Saved messages: 12' in h.render();show('Explicit review returns to Ready',h,started)
 # User chooses a new ID after reviewing the interrupted attempt.
 h.edit(text);retry=dict(request,request_id='console-live-retry',max_output_tokens=32);assert h.action('send',confirmed=True,request=retry,owned_worker='observer-B');observer.send(h.wire[-1]['packet']);h.edit('Draft while the real reply arrives.');show('New explicit Send retains previous transcript',h,started)
 response=observer.get();checks['real_native_reply']=response.get('status')=='completed' and response.get('generation',{}).get('input_tokens')==531;assert h.reply(response);show('Real committed reply, still awaiting saved-session review',h,started)
 checks['stop_after_reply_blocked']=not h.action('stop',confirmed=True)
 _,final_snapshot=dispatch_snapshot(h,observer);checks['full_history_visible']='Saved messages: 14' in h.render() and len(final_snapshot['history'])==14
 cache_before=h.snapshots.copy();checks['stale_actual_snapshot_ignored']=not h.snapshot(old_event['ticket'],old_snapshot) and h.snapshots==cache_before;show('Delayed old snapshot does not erase current transcript',h,started)
 assert h.action('release',confirmed=True);checks['final_draft_retained']=h.ui.view()['draft']=='Draft while the real reply arrives.';checks['ready_with_saved_history']='Ready' in h.render() and 'Saved messages: 14' in h.render();show('Ready after explicit review',h,started)
 observer.close();owner.close();receipt=next(json.loads(x.split(' ',1)[1]) for x in (root/'observer-stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '));checks['exact_one_completed_native_generation']=len(receipt['native_calls'])==1 and receipt['native_calls'][0]['returncode']==0
 with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as db:row=db.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone()
 checks['ledger_and_store_preserved']=row[0]==7 and len(json.loads(row[1]))==14 and len(json.loads(row[2]))==2 and row[3] is None
 (root/'console.txt').write_text('REAL ENDPOINT SCENARIO; scripted explicit user actions; no GUI.\n\n'+'\n\n'.join(f['label']+'\n'+f['text'] for f in frames)+'\n')
 result=dict(passed=all(checks.values()),checks=checks,frames=frames,reply=response,provenance='Console harness with real endpoint snapshot/recovery/native replies and one real owned-worker stop. Control reply deliberately withheld, not a network-fault emulator. First history is the verified six-turn fixture; one subsequent native reply is newly generated. No GUI integration or production activation.')
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='frames'},indent=2));assert result['passed']
finally:
 for endpoint in (owner,observer):
  if endpoint.p.poll() is None:endpoint.p.terminate();endpoint.p.wait(timeout=10)
