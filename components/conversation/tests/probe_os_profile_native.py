"""Actual imported Nix receipt + AI-DSL -> Omega/Motto/Granite and durable replay."""
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
    request=dict(api_version=2,op='turn',session_id='os-profile',request_id='query',expected_revision=0,
        text='Summarize the imported OS profile observation and AI-DSL search in two brief sentences. Are running-system state and service execution established?',
        context=[],max_output_tokens=96,cognitive_tasks=[
            {'component':'ai_dsl','request':{'version':1,'goal':'speech_emotion','depth':4}},
            {'component':'os_state','request':{'version':1,'operation':'query_imported_profile'}}])
    mutation={**request,'request_id':'mutation','expected_revision':1,
              'cognitive_tasks':[{'component':'os_state','request':{'version':1,'operation':'activate'}}]}
    followup=dict(api_version=2,op='turn',session_id='os-profile',request_id='recall',expected_revision=1,
        text="What source revision and machine did the imported OS record mention, and does it establish this computer's running system? Answer briefly.",
        context=[],max_output_tokens=96)
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
    replies,record=run('turns',[request,mutation,followup]);replay,replay_record=run('restart',[request,followup])
    with Store(db) as store:state=store.snapshot('os-profile',include_cognition=True)
    structured={row['component']:row['result'] for row in replies[0].get('cognitive_results',[])}
    os_result=structured.get('os_state',{});ai_result=structured.get('ai_dsl',{})
    checks={
        'completed':replies[0]['status']=='completed',
        'imported_observation_identity':os_result.get('source_revision')==3 and os_result.get('latest_observation',{}).get('phase')=='observed',
        'no_running_system_or_mutation_authority':all(os_result.get(key) is False for key in
            ('current_host_state_established','system_activation_established','running_system_established','health_established','mutation_authority','native_nix_reexecuted_here')),
        'ai_search_no_service_execution':ai_result.get('native_proof_count')==2 and ai_result.get('executed_services')==0,
        'two_native_queries_two_model_motto':len(record['learning_receipts'])==2 and len(record['native_calls'])==2 and len(record['motto_receipts'])==2,
        'structured_matches_native_receipts':structured=={r['component']:r['response'] for r in record['learning_receipts']},
        'mutation_rejected_before_execution':replies[1].get('code')=='invalid_request',
        'ordinary_followup_completed':replies[2]['status']=='completed' and replies[2]['revision']==2,
        'ordinary_followup_recalls_source':'private-profile-gate' in replies[2]['text'].lower() and '3' in replies[2]['text'],
        'ordinary_followup_no_new_tasks':'cognitive_results' not in replies[2],
        'atomic_two_observations':state['revision']==2 and len(state['history'])==4 and len(state['cognitive_history'])==2,
        'restart_replay_no_execution':replay==[replies[0],replies[2]] and not replay_record['native_calls'] and not replay_record['learning_receipts'] and not replay_record['motto_receipts'],
    }
    output={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'replies':replies,
            'seconds':time.monotonic()-started,'executed_actions':0,'native_nix_reexecuted_here':False}
    (args.output/'result.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
    return int(output['status']!='passed')


if __name__=='__main__':raise SystemExit(main())
