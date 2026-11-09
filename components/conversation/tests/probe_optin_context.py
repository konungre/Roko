"""Actual v2 opt-in projection, atomic full history, replay and default isolation."""
import argparse,json,os,sqlite3,subprocess,sys,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('profile','source-db','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(root/'history.sqlite') as dst:src.backup(dst)
with sqlite3.connect(root/'history.sqlite') as db:
 before=db.execute("SELECT history,cognitive_history FROM sessions WHERE id='language'").fetchone()
original=json.loads(before[0]);ledger=json.loads(before[1])
current='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4
context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)]
def turn(rid,rev,text,session='language',policy=None,ctx=[]):
 value=dict(api_version=2,op='turn',session_id=session,request_id=rid,expected_revision=rev,text=text,context=ctx,max_output_tokens=32)
 if policy is not None:value['context_policy']=policy
 return value
optin=turn('optin',6,current,policy='extractive_v1',ctx=context)
changed=dict(optin,context_policy='complete')
requests=[turn('default-overflow',6,current,ctx=context),optin,optin,changed,turn('default-after',7,'Name both creatures again.'),dict(api_version=2,op='snapshot',session_id='language'),turn('small',0,'Say hello briefly.',session='small',policy='extractive_v1'),turn('default',0,'Say hello briefly.',session='default')]
data=''.join(json.dumps(x)+'\n' for x in requests);(root/'requests.jsonl').write_text(data)
env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
source=Path(__file__).resolve().parents[1]
with (root/'stdout.txt').open('wb') as out,(root/'stderr.txt').open('wb') as err:
 proc=subprocess.run([sys.executable,'-B',str(source/'durable_server.py')],input=data.encode(),stdout=out,stderr=err,env=env,timeout=600)
r=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
n=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
with sqlite3.connect(root/'history.sqlite') as db:after=db.execute("SELECT cognitive_history FROM sessions WHERE id='language'").fetchone()[0]
m=r[1].get('model_context',{})
canonical=json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
c={'protocol':proc.returncode==0 and len(r)==8,'default_refused_full':r[0].get('code')=='context_limit','optin_committed':r[1].get('status')=='completed' and r[1]['revision']==7,'loss_explicit':m.get('model_context_complete') is False and m.get('omitted_count',0)>0,'source_history_bound':m.get('full_history_sha256')==hashlib.sha256(canonical).hexdigest(),'token_count_matches_native':m.get('token_count')==r[1].get('generation',{}).get('input_tokens'),'recall':all(x in r[1].get('text','').lower() for x in ('fox','robin')),'exact_replay':r[2]==r[1],'policy_conflict':r[3].get('code')=='request_conflict','default_not_sticky':r[4].get('code')=='context_limit','full_authority_preserved':r[5]['history'][:12]==original and len(r[5]['history'])==14 and r[5]['history'][12]['content']==current,'ledger_unchanged':json.loads(after)==ledger,'small_optin_complete':r[6].get('status')=='completed' and r[6].get('model_context',{}).get('model_context_complete') is True,'default_schema_unchanged':r[7].get('status')=='completed' and 'model_context' not in r[7],'native_calls':len(n['native_calls'])==5,'no_new_nars':n['cognitive_receipts']==[],'mork_claims_only':len(n['mork_receipts'])==5,'real_ecan':len(n['ecan_receipts'])==2}
result={'passed':all(c.values()),'checks':c,'optin_response':r[1],'public_default_changed':False,'executed_actions':0}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
