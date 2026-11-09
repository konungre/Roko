"""Explicit native load/recovery qualification; not an automatic application retry loop."""
import pathlib,sys,json,subprocess,sqlite3,os,time
import argparse
parser=argparse.ArgumentParser(description='Real native budget768 contention/cancellation/recovery; source checkpoint stays read-only')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
args=parser.parse_args();root=args.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
code=pathlib.Path(__file__).resolve().parents[1];fixture=args.source_db.resolve()
with sqlite3.connect(fixture.as_uri()+'?mode=ro',uri=True) as s,sqlite3.connect(root/'history.sqlite') as d:s.backup(d)
def state(session):
 with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as s:r=s.execute('select revision,history,cognitive_history,pending from sessions where id=?',(session,)).fetchone()
 return dict(revision=r[0],history=json.loads(r[1]),cognitive_history=json.loads(r[2]),pending=r[3])
before=state('language');
if before['revision']!=6 or len(before['history'])!=12 or len(before['cognitive_history'])!=2 or before['pending'] is not None:raise ValueError('Requires verified six-turn checkpoint with two observations and no pending claim')
(root/'before.json').write_text(json.dumps(before,indent=2)+'\n')
env={**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
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
snap=lambda session:dict(api_version=2,op='snapshot',session_id=session)
a=Endpoint('owner');b=Endpoint('observer');checks={}
try:
 for endpoint in (a,b):assert endpoint.call(dict(api_version=2,op='limits',session_id='language'))['input_token_limit']==768
 original=dict(api_version=2,op='turn',session_id='language',request_id='shared',expected_revision=6,text='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4,context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)],max_output_tokens=128);a.send(original)
 start=time.monotonic();supervisor=None;resident=[]
 while time.monotonic()-start<90:
  for line in (root/'owner-stderr.txt').read_text().splitlines():
   if line.startswith('ROKO_NATIVE_STARTED '):supervisor=json.loads(line.split(' ',1)[1])['supervisor_pid']
  resident=group(supervisor) if supervisor else []
  if any(x['rss']>3*1024**3 and x['cpu_ticks']>20 for x in resident):break
  if a.p.poll() is not None:raise RuntimeError('Owner exited before cancellation')
  time.sleep(.03)
 checks['resident_real_inference']=any(x['rss']>3*1024**3 and x['cpu_ticks']>20 for x in resident)
 pending=b.call(original);busy=b.call({**original,'request_id':'competing'});recovery=dict(api_version=2,op='recover',session_id='language',request_id='shared',expected_revision=6);live_recovery=b.call(recovery)
 checks['same_request_pending']=pending.get('code')=='pending';checks['different_request_busy']=busy.get('code')=='busy';checks['live_recovery_refused']=live_recovery.get('code')=='busy'
 a.p.terminate();a.p.wait(timeout=10);a.p.stdin.close();start=time.monotonic()
 while supervisor and group(supervisor) and time.monotonic()-start<10:time.sleep(.03)
 remaining=group(supervisor) if supervisor else []
 checks['native_descendants_gone']=not remaining;checks['no_turn_reply_before_cancel']=len((root/'owner-stdout.txt').read_text().splitlines())==1
 pending_after=b.call(snap('language'));interrupted=b.call(recovery);recovered_snapshot=b.call(snap('language'));terminal=b.call(original)
 checks['dead_claim_visible']=pending_after['pending']=='shared';checks['explicit_recovery']=interrupted.get('status')=='interrupted';checks['recovery_preserves_history']=recovered_snapshot['history']==before['history'] and recovered_snapshot['revision']==6 and recovered_snapshot['pending'] is None;checks['cancelled_id_terminal']=terminal.get('code')=='interrupted'
 retry={**original,'request_id':'recovered','max_output_tokens':32};completed=b.call(retry);replay=b.call(retry)
 checks['explicit_new_id_recovers']=completed.get('status')=='completed' and completed.get('revision')==7 and 512<completed['generation']['input_tokens']<=768;checks['recovered_replay_exact']=replay==completed
 beta=dict(api_version=2,op='turn',session_id='secondary',request_id='shared',expected_revision=0,text='The project codename is Cedar. Reply only with the codename.',context=[],max_output_tokens=32)
 first=b.call(beta);follow={**beta,'request_id':'followup','expected_revision':1,'text':'What project codename did I give you? Reply only with it.'};second=b.call(follow);second_replay=b.call(follow)
 stale=b.call({**retry,'request_id':'stale-client'});lang=b.call(snap('language'));secondary=b.call(snap('secondary'))
 checks['same_id_other_session_admitted']=first.get('revision')==1;checks['real_multi_turn_recall']=second.get('revision')==2 and 'cedar' in second['text'].lower();checks['secondary_replay_exact']=second_replay==second;checks['stale_cas_refused']=stale.get('code')=='stale_revision';checks['language_history_and_cognition']=len(lang['history'])==14 and lang['history'][:12]==before['history'] and state('language')['cognitive_history']==before['cognitive_history'];checks['sessions_isolated']=len(secondary['history'])==4 and not any('fox' in x['content'].lower() for x in secondary['history']);checks['no_pending']=lang['pending'] is None and secondary['pending'] is None
 b.close();a.close()
 receipt=next(json.loads(x.split(' ',1)[1]) for x in (root/'observer-stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '));checks['exact_three_generations']=len(receipt['native_calls'])==3 and all(x['returncode']==0 for x in receipt['native_calls'])
 checks['native_memory_caps_unchanged']='if rss > 5 * 1024**3:' in (code/'fresh_supervise.py').read_text()
 result=dict(passed=all(checks.values()),checks=checks,resident_before=resident,native_after=remaining,owner_returncode=a.p.returncode,replies=dict(recovered=completed,secondary_first=first,secondary_second=second),provenance='Two warm real endpoint clients, serial successful native generation plus cancellation during resident inference; no synthetic conversation replies and no production activation')
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
finally:
 for endpoint in (a,b):
  if endpoint.p.poll() is None:endpoint.p.terminate();endpoint.p.wait(timeout=10)
