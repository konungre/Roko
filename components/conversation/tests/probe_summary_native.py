"""Experimental exact-token summary qualification; never commits a public v2 turn."""
import argparse,hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from fresh import FreshProvider,load_profile,GenerationError
from fresh_ecan import rank_candidates
from mork_v2 import retrieve_history,history_digest
from recovered import render,system_message
from context_summary import build_summary
p=argparse.ArgumentParser(description=__doc__)
for key in ('profile','source-db','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
profile=load_profile(a.profile);provider=FreshProvider(profile);provider.allow_partial=True;provider.max_tokens=32
with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as db:
 before=list(db.iterdump());row=db.execute("SELECT revision,history,cognitive_history FROM sessions WHERE id='language'").fetchone()
revision,history,ledger=row[0],json.loads(row[1]),json.loads(row[2])
history,mork=retrieve_history(history,dict(session_id='language',request_id='summary-experiment',revision=revision,history_sha256=history_digest(history)),profile)
rank,ecan=rank_candidates([dict(id='ctx_0',sti=100,lti=10,stimulus=0)],profile=profile)
context=[dict(id='brief',text='Answer in one short sentence.')] if rank['focus']==['ctx_0'] else []
counts=[]
def count(prompt):
 stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
 cmd=[profile['python'],'-B',str(SOURCE/'fresh_supervise.py'),'--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','30','--',profile['infer'],'--model',f'/proc/{os.getpid()}/fd/{provider.fd}','--count-tokens']
 result=subprocess.run(cmd,input=prompt.encode(),capture_output=True,start_new_session=True,timeout=40,check=True)
 value=json.loads(result.stdout);assert set(value)=={'input_tokens'} and b'descendants_cleaned=1' in result.stderr
 counts.append(dict(input_tokens=value['input_tokens'],prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),stderr=result.stderr.decode()))
 (root/'tokenizer-counts.json').write_text(json.dumps(counts,indent=2)+'\n')
 return value['input_tokens']
current='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4
full=[dict(role='system',content=system_message(SimpleNamespace(context=context,cognitive_context=ledger)))]+history+[dict(role='user',content=current)]
full_count=count(render(full));assert full_count>512,full_count
try:provider.chat(full)
except GenerationError as error:assert error.code=='context_limit'
else:raise AssertionError('Full prompt unexpectedly admitted')
messages,provenance=build_summary(history,current,count_tokens=count,budget=512,recent_pairs=1,cognitive_context=ledger,context=context)
answer=provider.chat(messages);provider.verify_model();provider.close()
with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as db:after=list(db.iterdump())
checks={'full_native_over_budget':full_count>512,'summary_exact_fit':provenance['token_count']<=512,'generation_count_matches_tokenizer':provider.last_generation['input_tokens']==provenance['token_count'],'complete_authoritative_history_unchanged':before==after,'all_older_users_covered':len(provenance['excerpts'])==len(history)//2-1,'model_context_explicitly_lossy':provenance['model_context_complete'] is False,'recall':all(x in answer.lower() for x in ('fox','robin')),'mork_complete':mork['indexed_messages']==len(history) and not mork['history_omitted'],'real_ecan':len(context)==1,'both_nars_observations_retained':len(ledger)==2}
r={'passed':all(checks.values()),'checks':checks,'full_input_tokens':full_count,'summary_provenance':provenance,'answer':answer,'generation':provider.last_generation,'native_calls':provider.receipts,'tokenizer_calls':counts,'mork_receipt':mork,'ecan_receipt':ecan,'public_API_activated':False,'database_commits':0,'executed_actions':0}
(root/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':r['passed'],'checks':checks,'full_input_tokens':full_count,'summary_tokens':provenance['token_count'],'answer':answer},indent=2));raise SystemExit(0 if r['passed'] else 1)
