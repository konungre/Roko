"""Actual upstream AI-DSL -> Omega -> Motto -> Granite, then restart replay."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from durable_store import Store


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    db=args.output/'history.sqlite';started=time.monotonic()
    request=dict(api_version=2,op='turn',session_id='ai-dsl',request_id='search',expected_revision=0,
        text='What did the speech/emotion AI-DSL search establish? Say whether any service actually ran.',context=[],max_output_tokens=64,
        cognitive_tasks=[{'component':'ai_dsl','request':{'version':1,'goal':'speech_emotion','depth':4}}])
    changed={**request,'cognitive_tasks':[{'component':'ai_dsl','request':{'version':1,'goal':'speech_emotion','depth':3}}]}
    def run(label,requests):
        with (args.output/(label+'.stderr')).open('xb') as err:
            proc=subprocess.run([sys.executable,'-B',str(SOURCE/'durable_server.py')],
                input=b''.join(json.dumps(r).encode()+b'\n' for r in requests),stdout=subprocess.PIPE,stderr=err,
                env={**os.environ,'ROKO_FRESH_PROFILE':args.profile,'ROKO_HISTORY_DB':str(db)},timeout=240)
        (args.output/(label+'.stdout')).write_bytes(proc.stdout)
        if proc.returncode:raise ValueError('Native server failed')
        replies=[json.loads(r) for r in proc.stdout.splitlines()]
        records=[json.loads(r.split(' ',1)[1]) for r in (args.output/(label+'.stderr')).read_text().splitlines() if r.startswith('ROKO_FRESH_CONVERSATION ')]
        if len(replies)!=len(requests) or len(records)!=1:raise ValueError('Native protocol count')
        return replies,records[0]
    replies,record=run('turns',[request,changed]);replay,replay_record=run('restart',[request])
    with Store(db) as store:state=store.snapshot('ai-dsl',include_cognition=True)
    structured=replies[0].get('cognitive_results',[])
    result=structured[0]['result'] if len(structured)==1 else {}
    checks={
        'completed':replies[0]['status']=='completed',
        'native_search_results':result.get('native_proof_count')==2 and len(result.get('accepted',[]))==1 and len(result.get('rejected',[]))==1,
        'no_services_executed':result.get('executed_services')==0 and result.get('service_results','missing') is None,
        'one_component_one_model_one_motto':len(record['learning_receipts'])==1 and len(record['native_calls'])==1 and len(record['motto_receipts'])==1,
        'structured_matches_native_receipt':bool(structured) and structured[0]['result']==record['learning_receipts'][0]['response'],
        'changed_request_conflict':replies[1].get('code')=='request_conflict',
        'atomic_observation':state['revision']==1 and len(state['history'])==2 and len(state['cognitive_history'])==1,
        'restart_replay_no_execution':replay==[replies[0]] and not replay_record['native_calls'] and not replay_record['learning_receipts'] and not replay_record['motto_receipts'],
    }
    output={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'replies':replies,'seconds':time.monotonic()-started,'executed_actions':0}
    (args.output/'result.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
    return int(output['status']!='passed')


if __name__=='__main__':raise SystemExit(main())
