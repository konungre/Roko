"""Continue a copied native four-turn checkpoint through two bounded MORK batches."""
import argparse,json,os,sqlite3,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('profile','source-db','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(root/'history.sqlite') as dst:src.backup(dst)
def turn(rid,rev):return dict(api_version=2,op='turn',session_id='language',request_id=rid,expected_revision=rev,text='Name both creatures again, briefly.',context=[],max_output_tokens=16)
fifth=turn('fifth-expanded',4);sixth=turn('sixth-expanded',5)
requests=[fifth,sixth,sixth,dict(api_version=2,op='snapshot',session_id='language'),dict(api_version=2,op='limits',session_id='language')]
data=''.join(json.dumps(x)+'\n' for x in requests);(root/'requests.jsonl').write_text(data)
env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
with (root/'stdout.txt').open('wb') as out,(root/'stderr.txt').open('wb') as err:
 proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'durable_server.py')],input=data.encode(),stdout=out,stderr=err,env=env,timeout=420)
r=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
n=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
c={'protocol':proc.returncode==0 and len(r)==5,'fifth_complete':r[0].get('status')=='completed' and r[0]['revision']==5,'sixth_complete':r[1].get('status')=='completed' and r[1]['revision']==6,'recall':all(term in reply.get('text','').lower() for term in ('fox','robin') for reply in r[:2]),'exact_replay':r[2]==r[1],'complete_history':len(r[3]['history'])==12 and r[3]['revision']==6,'capacity_two_left':r[4]['remaining_exchanges']==2,'native_mork_complete':len(n['mork_receipts'])==2 and [x['indexed_messages'] for x in n['mork_receipts']]==[8,10],'native_batch_counts':[x['batch_count'] for x in n['mork_receipts']]==[1,2],'native_calls':len(n['native_calls'])==2 and all(x.get('model_verified_before_history_commit') for x in n['native_calls']),'cognition_preserved':len(n['cognitive_history'])==2 and n['cognitive_receipts']==[]}
result={'passed':all(c.values()),'checks':c,'replies':r[:2],'mork_receipts':n['mork_receipts'],'executed_actions':0}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
