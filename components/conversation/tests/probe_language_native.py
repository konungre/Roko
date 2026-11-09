"""Two real Omega/PeTTa/Granite turns with expanded controlled-language inference.

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
    requests=[{'text':'All robins are birds. All birds are animals. What follows?','context':[]},
              {'text':'Every mammal is an animal. A red fox is a mammal. What follows?','context':[]}]
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
        if len(cognition)!=2:raise ValueError('Exactly two NARS invocations required')
        history=receipt['history']
        checks['session_history']=len(history)==4 and all(history[2*i]['content']==r['text'] for i,r in enumerate(requests))
        for i,observed in enumerate(cognition):
            native=observed['receipt'];packet=json.loads(native['stdout'])
            checked=response_from_rows(observed['request'],packet['native_rows'])
            checks[f'native_nars_{i}']=native['status']=='passed' and native['returncode']==0
            checks[f'provenance_{i}']=checked==observed['response'] and packet['request']==observed['request']
            checks[f'snapshot_{i}']=observed['snapshot_sha256']==hashlib.sha256(canonical(
                {'text':requests[i]['text'],'history':history[:2*i]})).hexdigest()
            system=system_message(SimpleNamespace(context=[],cognitive_context=[c['prompt_context'] for c in cognition[:i+1]]))
            prompt=render([{'role':'system','content':system}]+history[:2*i+1])
            checks[f'prompt_dataflow_{i}']=calls[i]['prompt_sha256']==hashlib.sha256(prompt.encode()).hexdigest()
        checks['plural_answer']=bool(re.search(r'robins?\b',replies[0]['text'],re.I) and re.search(r'animals?\b',replies[0]['text'],re.I))
        checks['multiword_answer']=bool(re.search(r'red fox\b',replies[1]['text'],re.I) and re.search(r'animals?\b',replies[1]['text'],re.I))
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
