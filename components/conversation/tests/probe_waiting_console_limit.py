"""Explicit native console test; source checkpoint stays read-only."""
import pathlib,sys,json,sqlite3,subprocess,os,time
import argparse
parser=argparse.ArgumentParser(description='Explicit real endpoint console qualification; no graphical integration')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
config=parser.parse_args();root=config.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
code=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(code))
from console_harness import ConsoleHarness
with sqlite3.connect(config.source_db.resolve().as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(root/'error-history.sqlite') as b:a.backup(b)
with sqlite3.connect((root/'error-history.sqlite').as_uri()+'?mode=ro',uri=True) as db:
 row=db.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone()
if row is None or row[0]!=7 or len(json.loads(row[1]))!=14 or len(json.loads(row[2]))!=2 or row[3] is not None:raise ValueError('Unexpected qualified source checkpoint')
env={**os.environ,'ROKO_FRESH_PROFILE':str(config.profile.resolve()),'ROKO_HISTORY_DB':str(root/'error-history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
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

endpoint=Endpoint('limit');checks={};frames=[]
try:
 endpoint.call(dict(api_version=2,op='limits',session_id='language'))
 text='Name both creatures. '+'x '*500;request=dict(api_version=2,op='turn',session_id='language',request_id='console-limit',expected_revision=7,text=text,context=[],max_output_tokens=32)
 h=ConsoleHarness(text);assert h.action('send',confirmed=True,request=request,owned_worker='limit-worker');endpoint.send(h.wire[-1]['packet']);h.edit('My revised draft after a long request.')
 frames.append(h.render());response=endpoint.get();checks['real_context_limit']=response.get('code')=='context_limit';assert h.error(response);frames.append(h.render());checks['readable_limit_message']='exceeds the active model input limit' in frames[-1];checks['draft_retained']='My revised draft' in frames[-1];checks['unknown_history_not_empty']='Saved messages: not yet inspected' in frames[-1]
 checks['stop_unavailable_after_finished_error']=not h.action('stop',confirmed=True) and h.stops==[]
 assert h.action('inspect',confirmed=True);event=h.wire[-1];snapshot=endpoint.call(event['packet']);assert h.snapshot(event['ticket'],snapshot);checks['real_history_unchanged']=snapshot['revision']==7 and snapshot['pending'] is None and len(snapshot['history'])==14
 assert h.action('release',confirmed=True);frames.append(h.render());checks['ready_keeps_draft_and_history']='Ready' in frames[-1] and 'Saved messages: 14' in frames[-1] and 'My revised draft' in frames[-1]
 endpoint.close();receipt=next(json.loads(x.split(' ',1)[1]) for x in (root/'limit-stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '));checks['no_successful_generation_on_error']=len(receipt['native_calls'])==1 and receipt['native_calls'][0]['returncode']==2 and receipt['native_calls'][0]['stdout_bytes']==0
 with sqlite3.connect((root/'error-history.sqlite').as_uri()+'?mode=ro',uri=True) as db:row=db.execute("select status from requests where request_id='console-limit'").fetchone()
 checks['failed_id_terminal']=row[0]=='failed'
 (root/'limit-console.txt').write_text('REAL ENDPOINT LIMIT ERROR; no successful model generation in this case.\n\n'+'\n\n'.join(frames)+'\n')
 result=dict(passed=all(checks.values()),checks=checks,response=response,provenance='Real endpoint context_limit against a copy of the prior live run database. Seeded six-turn fixture plus one earlier live native reply; no fresh successful generation in this error case. No GUI integration.')
 (root/'limit-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
finally:
 if endpoint.p.poll() is None:endpoint.p.terminate();endpoint.p.wait(timeout=10)
