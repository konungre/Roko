"""Explicit single-turn native combination and same-request replay probe."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from learning import canonical
from durable_store import Store

def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False);db=a.output/'history.sqlite'
 rows=json.loads(Path(__file__).with_name('learning_fixtures.json').read_bytes())
 request=dict(api_version=2,op='turn',session_id='combined',request_id='all-three',expected_revision=0,
  text='Briefly summarize the three component results.',context=[],max_output_tokens=64,
  cognitive_tasks=[{'component':r['component'],'request':r['request']} for r in rows])
 (a.output/'request.json').write_bytes(canonical(request));start=time.monotonic();checks={};error=None;replies=[]
 with (a.output/'stderr').open('xb') as err:
  proc=subprocess.Popen([sys.executable,'-B',str(SOURCE/'durable_server.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,
   env={**os.environ,'ROKO_FRESH_PROFILE':a.profile,'ROKO_HISTORY_DB':str(db)})
  try:out,_=proc.communicate(canonical(request)+b'\n'+canonical(request)+b'\n',timeout=240)
  except BaseException:
   proc.terminate()
   try:out,_=proc.communicate(timeout=8)
   except subprocess.TimeoutExpired:proc.kill();out,_=proc.communicate(timeout=3)
   raise
 (a.output/'stdout').write_bytes(out)
 try:
  replies=[json.loads(line) for line in out.decode().splitlines()]
  records=[json.loads(line.split(' ',1)[1]) for line in (a.output/'stderr').read_text().splitlines() if line.startswith('ROKO_FRESH_CONVERSATION ')]
  if proc.returncode or len(replies)!=2 or len(records)!=1:raise ValueError('Native protocol failure')
  record=records[0]
  checks['three_components_one_model']=len(record['learning_receipts'])==3 and len(record['native_calls'])==1
  checks['completed']=replies[0]['status']=='completed' and replies[0]['executed_actions']==0
  checks['exact_replay']=replies[0]==replies[1]
  checks['structured_results']=replies[0].get('cognitive_results')==[{'component':r['component'],'observation_id':r['prompt_context']['id'],'result':r['response']} for r in record['learning_receipts']]
  with Store(db) as store:state=store.snapshot('combined',include_cognition=True)
  checks['atomic_three_observation_commit']=state['revision']==1 and len(state['history'])==2 and len(state['cognitive_history'])==3
 except BaseException as exc:error=repr(exc)
 result=dict(status='passed' if error is None and all(checks.values()) else 'failed',checks=checks,error=error,replies=replies,seconds=time.monotonic()-start,executed_actions=0)
 (a.output/'result.json').write_bytes(canonical(result)+b'\n');print(json.dumps(result,indent=2))
 return int(result['status']!='passed')
if __name__=='__main__':raise SystemExit(main())
