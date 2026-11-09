"""Local native regression: staged NARS overflow, restart recovery, terminal ID.

Copies a verified synthetic six-turn database. Never modifies the source DB.
--audit-only verifies captured JSON/stdout/stderr without native execution.
"""
import argparse,json,sqlite3,pathlib,hashlib,sys,subprocess,os
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=pathlib.Path,required=True)
p.add_argument('--profile',type=pathlib.Path)
p.add_argument('--source-db',type=pathlib.Path)
p.add_argument('--audit-only',action='store_true')
a=p.parse_args();p=a.output.resolve()
if not a.audit_only:
 if not a.profile or not a.source_db:raise SystemExit('--profile and --source-db required')
 p.mkdir(mode=0o700,parents=True,exist_ok=False)
 with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(p/'history.sqlite') as dst:src.backup(dst)
 with sqlite3.connect(p/'history.sqlite') as db:
  state=db.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone()
 if state is None or state[0]!=6 or len(json.loads(state[1]))!=12 or len(json.loads(state[2]))!=2:raise SystemExit('Requires verified six-turn synthetic language fixture')
 (p/'before.json').write_text(json.dumps(state))
 def turn(rid,text):return dict(api_version=2,op='turn',session_id='language',request_id=rid,expected_revision=6,text=text,context=[],context_policy='extractive_v1',max_output_tokens=32)
 failed=turn('third-belief-overflow','A salmon is a fish. A fish is an animal. What follows?')
 recovered=turn('short-recovery','Name both creatures from our earlier conversation, briefly.')
 snapshot=dict(api_version=2,op='snapshot',session_id='language')
 env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(p/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
 server=pathlib.Path(__file__).resolve().parents[1]/'durable_server.py'
 for name,requests in [('failed',[failed,snapshot]),('recovery',[recovered,recovered,snapshot]),('terminal',[failed,snapshot])]:
  data=''.join(json.dumps(x)+'\n' for x in requests);(p/(name+'.jsonl')).write_text(data)
  with (p/(name+'.stdout.txt')).open('wb') as out,(p/(name+'.stderr.txt')).open('wb') as err:
   subprocess.run([sys.executable,'-B',str(server)],input=data.encode(),stdout=out,stderr=err,env=env,timeout=360,check=True)
 with sqlite3.connect(p/'history.sqlite') as db:(p/'database-state.json').write_text(json.dumps(list(db.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone())))
 with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as db:(p/'source-after.json').write_text(json.dumps(list(db.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone())))
before=json.loads((p/'before.json').read_text());history=json.loads(before[1]);ledger=json.loads(before[2])
def output(name):return [json.loads(x) for x in (p/(name+'.stdout.txt')).read_text().splitlines()]
def native(name):return next(json.loads(x.split(' ',1)[1]) for x in (p/(name+'.stderr.txt')).read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
f,r,t=output('failed'),output('recovery'),output('terminal');nf,nr,nt=native('failed'),native('recovery'),native('terminal')
if a.audit_only:
 state=json.loads((p/"database-state.json").read_text());source=json.loads((p/"source-after.json").read_text())
else:
 with sqlite3.connect(p/'history.sqlite') as d:state=d.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone()
 with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as d:source=list(d.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone())
c={'native_nars_executed_before_failure':len(nf['cognitive_receipts'])==1 and nf['cognitive_receipts'][0]['receipt']['status']=='passed','exact_budget_refusal':f[0].get('code')=='context_projection_limit' and len(nf['token_counter_calls'])==5 and all(x['input_tokens']>512 for x in nf['token_counter_calls']),'no_model_on_failed_plan':nf['native_calls']==[],'failed_snapshot_unchanged':f[1]['revision']==6 and f[1]['history']==history and f[1]['pending'] is None,'failed_ledger_preserved':nf['cognitive_history']==ledger,'restart_recovery':r[0].get('status')=='completed' and r[0]['revision']==7,'complete_recovery_context':r[0]['model_context']['model_context_complete'] is True and r[0]['generation']['input_tokens']<=512,'recall':all(x in r[0]['text'].lower() for x in ('fox','robin')),'exact_replay':r[0]==r[1],'full_prior_history_retained':r[2]['history'][:12]==history and len(r[2]['history'])==14,'new_failed_belief_not_committed':json.loads(state[2])==ledger and nr['cognitive_receipts']==[],'terminal_failed_id':t[0].get('code')=='failed','terminal_no_native_work':all(nt[k]==[] for k in ('native_calls','cognitive_receipts','mork_receipts','ecan_receipts','token_counter_calls')),'original_checkpoint_unchanged':source==before}
result={'passed':all(c.values()),'checks':c,'failed_minimum_input_tokens':min(x['input_tokens'] for x in nf['token_counter_calls']),'recovery_reply':r[0],'evidence_provenance':'local execution; not independent reproduction','executed_actions':0}
(p/('audit-result.json' if a.audit_only else 'result.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
