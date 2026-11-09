"""Two real Omega/PeTTa/Granite turns with a genuine NARS inference on turn one.

This is an explicit native probe, never discovered by the unit-test pattern.
"""
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
SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
sys.path.insert(0,str(SOURCE.parents[1]))
from recovered import render,system_message
from components.nars_hyperon.source.contract import canonical,response_from_rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    requests=[{'text':'A robin is a bird. A bird is an animal. What follows?','context':[]},
              {'text':'What creature did I mention, and what two kinds does it belong to?','context':[]}]
    (args.output/'requests.json').write_bytes(canonical(requests))
    start=time.monotonic();error=None;out=b''
    with (args.output/'stderr.txt').open('xb') as diagnostic:
        proc=subprocess.Popen([sys.executable,'-B',str(SOURCE/'fresh_server.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostic,
            env={**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve()),'PYTHONDONTWRITEBYTECODE':'1'})
        try:out,_=proc.communicate(b'\n'.join(canonical(r) for r in requests)+b'\n',timeout=420)
        except BaseException as exc:
            error=exc;proc.terminate()
            try:out,_=proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill();out,_=proc.communicate(timeout=3)
    (args.output/'stdout.txt').write_bytes(out)
    checks={};receipt=None;replies=[]
    try:
        replies=[json.loads(line) for line in out.decode().splitlines()]
        diagnostics=(args.output/'stderr.txt').read_text()
        records=[json.loads(line.removeprefix('ROKO_FRESH_CONVERSATION ')) for line in diagnostics.splitlines()
                 if line.startswith('ROKO_FRESH_CONVERSATION ')]
        checks['response_schema']=len(replies)==2 and all(set(r)=={'text','context_ids','executed_actions'}
            and type(r['text']) is str and bool(r['text'].strip()) and r['context_ids']==[]
            and type(r['executed_actions']) is int and r['executed_actions']==0 for r in replies)
        if len(records)!=1:raise ValueError('Missing final native session receipt')
        receipt=records[0];calls=receipt['native_calls'];cognition=receipt['cognitive_receipts']
        checks['two_model_calls']=len(calls)==2 and all(c['returncode']==0
            and c.get('model_verified_before_history_commit') is True
            and 'descendants_cleaned=1' in c['stderr'] for c in calls)
        if len(cognition)!=1:raise ValueError('Exactly one NARS invocation required')
        observed=cognition[0];native=observed['receipt'];packet=json.loads(native['stdout'])
        checked=response_from_rows(observed['request'],packet['native_rows'])
        checks['actual_nars_rows']=native['status']=='passed' and native['returncode']==0
        checks['nars_provenance']=checked==observed['response'] and packet['request']==observed['request']
        checks['snapshot_binding']=observed['snapshot_sha256']==hashlib.sha256(canonical(
            {'text':requests[0]['text'],'history':[]})).hexdigest()
        first_system=system_message(SimpleNamespace(context=[],cognitive_context=[observed['prompt_context']]))
        first_prompt=render([{'role':'system','content':first_system},
                             {'role':'user','content':requests[0]['text']}])
        checks['native_prompt_contains_nars']=calls[0]['prompt_sha256']==hashlib.sha256(first_prompt.encode()).hexdigest()
        history=receipt['history']
        checks['session_history']=len(history)==4 and history[0]['content']==requests[0]['text'] and history[2]['content']==requests[1]['text']
        second_system=system_message(SimpleNamespace(context=[],cognitive_context=[observed['prompt_context']]))
        second_prompt=render([{'role':'system','content':second_system}]+history[:3])
        checks['followup_native_history']=calls[1]['prompt_sha256']==hashlib.sha256(second_prompt.encode()).hexdigest()
        checks['robin_recall']=len(replies)==2 and all(re.search(r'\b'+term+r'\b',replies[1]['text'],re.I)
            for term in ('robin','bird','animal'))
        checks['complete_sentences']=len(replies)==2 and all(r['text'].strip().endswith(('.','!','?')) for r in replies)
    except Exception as exc:
        if error is None:error=exc
    result={'status':'passed' if error is None and proc.returncode==0 and checks and all(checks.values()) else 'failed',
        'returncode':proc.returncode,'seconds':time.monotonic()-start,'checks':checks,'replies':replies,
        'profile_sha256':hashlib.sha256(args.profile.read_bytes()).hexdigest(),
        'full_nars':False,'full_autonomous_omega':False,'guest_tested':False,'executed_actions':0}
    if receipt is not None:
        result['native_call_seconds']=[c['seconds'] for c in receipt['native_calls']]
        result['cognitive_receipts']=receipt['cognitive_receipts']
    if error is not None:result['error']=repr(error)
    (args.output/'result.json').write_bytes(canonical(result)+b'\n')
    print(json.dumps({'status':result['status'],'seconds':result['seconds'],'checks':checks,'replies':replies},indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
