"""Real context rejection at revision three and fourth-turn recovery."""
import argparse,json,os,sqlite3,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('profile','source-db','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(root/'history.sqlite') as dst:src.backup(dst)
def turn(rid,text):return dict(api_version=2,op='turn',session_id='language',request_id=rid,expected_revision=3,text=text,context=[],max_output_tokens=32)
requests=[turn('capacity-overflow','a b '*1000),turn('capacity-fourth','Name the two creatures again, briefly.'),dict(api_version=2,op='snapshot',session_id='language')]
data=''.join(json.dumps(x)+'\n' for x in requests);(root/'requests.jsonl').write_text(data)
env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
with (root/'stdout.txt').open('wb') as out,(root/'stderr.txt').open('wb') as err:
 r=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'durable_server.py')],input=data.encode(),stdout=out,stderr=err,env=env,timeout=420)
replies=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
n=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
checks={'protocol':r.returncode==0 and len(replies)==3,'input_limit_explicit':replies[0].get('code')=='context_limit','unchanged_revision_recovers':replies[1].get('status')=='completed' and replies[1]['revision']==4,'recall':all(x in replies[1].get('text','').lower() for x in ('fox','robin')),'eight_messages_retained':len(replies[2]['history'])==8 and replies[2]['pending'] is None,'native_mork_complete':len(n['mork_receipts'])==2 and all(x['indexed_messages']==6 for x in n['mork_receipts']),'both_observations_retained':len(n['cognitive_history'])==2 and n['cognitive_receipts']==[],'native_calls':len(n['native_calls'])==2,'successful_model_verified':n['native_calls'][1].get('model_verified_before_history_commit') is True}
result={'passed':all(checks.values()),'checks':checks,'reply':replies[1],'executed_actions':0}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
