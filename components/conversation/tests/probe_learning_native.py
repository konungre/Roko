"""Explicit real MetaMo/AIRIS/NACE → Omega/Granite v2 probe, not unittest."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from learning import canonical,digest
from recovered import render,system_message
from durable_store import Store


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    db=a.output/'history.sqlite';checks={};phases=[];error=None;started=time.monotonic()
    env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(db)}
    fixtures=json.loads(Path(__file__).with_name('learning_fixtures.json').read_bytes())
    turns=[dict(api_version=2,op='turn',session_id=r['component'],request_id='first',expected_revision=0,
        text=r['text'],context=[],max_output_tokens=64,cognitive_tasks=[{'component':r['component'],'request':r['request']}]) for r in fixtures]
    def run(name,requests):
        folder=a.output/name;folder.mkdir();(folder/'requests.json').write_bytes(canonical(requests))
        with (folder/'stderr').open('xb') as err:
            proc=subprocess.Popen([sys.executable,'-B',str(SOURCE/'durable_server.py')],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=err,env=env)
            try:out,_=proc.communicate(b'\n'.join(canonical(r) for r in requests)+b'\n',timeout=600)
            except BaseException:
                proc.terminate()
                try:out,_=proc.communicate(timeout=8)
                except subprocess.TimeoutExpired:proc.kill();out,_=proc.communicate(timeout=3)
                (folder/'stdout').write_bytes(out);raise
        (folder/'stdout').write_bytes(out)
        replies=[json.loads(x) for x in out.decode().splitlines()]
        records=[json.loads(x.split(' ',1)[1]) for x in (folder/'stderr').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION ')]
        if proc.returncode or len(replies)!=len(requests) or len(records)!=1:raise ValueError('Native protocol/finalization failed in '+name)
        r=records[0];phases.append({'name':name,'replies':replies,'model_calls':len(r['native_calls']),'component_calls':len(r['learning_receipts'])})
        print(json.dumps(phases[-1]),flush=True);return replies,r
    try:
        replies,r=run('native-components',turns)
        checks['three_actual_model_and_component_calls']=len(r['native_calls'])==len(r['learning_receipts'])==3
        checks['no_unrequested_nars']=not r['cognitive_receipts']
        for turn,reply,call,receipt in zip(turns,replies,r['native_calls'],r['learning_receipts']):
            name=turn['session_id'];obs=receipt['prompt_context']
            checks[name+'_completed']=reply['status']=='completed' and reply['revision']==1 and reply['executed_actions']==0
            checks[name+'_native_verified']=receipt['status']=='passed' and call.get('model_verified_before_history_commit') is True and 'descendants_cleaned=1' in call['stderr'] and 'descendants_cleaned=1' in receipt['stderr']
            checks[name+'_binding']=receipt['binding']==dict(session_id=name,request_id='first',revision=0) and receipt['request']==turn['cognitive_tasks'][0]['request']
            prompt=render([{'role':'system','content':system_message(SimpleNamespace(context=[],cognitive_context=[obs]))},{'role':'user','content':turn['text']}])
            checks[name+'_native_prompt']=call['prompt_sha256']==hashlib.sha256(prompt.encode()).hexdigest()
            with Store(db) as store:state=store.snapshot(name,include_cognition=True)
            checks[name+'_atomic_commit']=state['revision']==1 and len(state['history'])==2 and state['cognitive_history']==[obs]
        checks['airis_answer_labels']=bool(re.search(r'step\s*=\s*8\b',replies[1]['text'],re.I) and re.search(r'hold\s*=\s*7\b',replies[1]['text'],re.I))
        checks['structured_native_results']=all(reply.get('cognitive_results')==[{'component':receipt['component'],'observation_id':receipt['prompt_context']['id'],'result':receipt['response']}] for reply,receipt in zip(replies,r['learning_receipts']))
        checks['metamo_result']=r['learning_receipts'][0]['response']['selected_proposal_id']=='act2'
        checks['airis_result']=r['learning_receipts'][1]['response']['predictions']['learned']=={'step':8,'hold':7}
        checks['nace_result']=r['learning_receipts'][2]['response']['prediction']['values'][0]==1
        replay,again=run('restart-replay',turns)
        checks['restart_replay_no_native']=replay==replies and not again['native_calls'] and not again['learning_receipts']
        overflow={**turns[1],'session_id':'overflow','text':'a b c d '*450}
        failed,record=run('model-reject',[overflow])
        with Store(db) as store:state=store.snapshot('overflow',include_cognition=True)
        checks['model_failure_after_actual_component']=failed[0].get('code')=='context_limit' and len(record['learning_receipts'])==1 and record['learning_receipts'][0]['status']=='passed'
        checks['failed_turn_no_ledger_commit']=state==dict(revision=0,history=[],cognitive_history=[],pending=None)
    except BaseException as exc:error=repr(exc)
    result=dict(status='passed' if error is None and checks and all(checks.values()) else 'failed',checks=checks,
        error=error,phases=phases,seconds=time.monotonic()-started,profile_sha256=hashlib.sha256(a.profile.read_bytes()).hexdigest(),
        executed_actions=0,full_components=False,guest_tested=False,ecan_qualified=False,mork_qualified=False)
    (a.output/'result.json').write_bytes(canonical(result)+b'\n');print(json.dumps(result,indent=2))
    return int(result['status']!='passed')
if __name__=='__main__':raise SystemExit(main())
