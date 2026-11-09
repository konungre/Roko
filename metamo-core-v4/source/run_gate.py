"""One finite native compatibility attempt, following exact parent admission."""
import argparse
import hashlib
import json
import math
import signal
import time
from fixtures import cases
from contract import canonical, parse_request
from reference_oracle import score
from gateway import run_native, verify_inputs
from paths import ROOT

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--admission',required=True)
    args=parser.parse_args()
    out=ROOT/'proof/native-attempt-001.json'
    marker=ROOT/'proof/native-started-001.json'
    if out.exists() or marker.exists(): raise ValueError('Attempt already consumed; no automatic retry')
    started=time.monotonic();deadline=started+90;receipts=[];checks=[]
    def interrupted(number,frame): raise InterruptedError('Gate termination signal '+str(number))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGALRM): signal.signal(sig,interrupted)
    result={'version':1,'manifest_sha256':args.admission,'scope':'upstream MAGUS scoring and DecisionMonad subset',
            'native_receipts':receipts,'checks':checks,'model_started':False,'VM_started':False,'guest_tested':False,
            'executed_actions':0,'authorizes_actions':False,'state_changed':False,'full_metamo_cycle_tested':False,
            'posthash_status':'not-completed','historical_receipts_reused':False,
            'parent_death_tested':False,'detached_descendant_containment':False,
            'outer_budget_kind':'cooperative monotonic90s incl hashes, with one-shot90s signal; not hard filesystem syscall interruption'}
    try:
        verify_inputs(args.admission,deadline-3)
        with marker.open('x') as stream:
            json.dump({'manifest_sha256':args.admission,'maximum_native_processes':8,'attempt':1},stream)
        signal.setitimer(signal.ITIMER_REAL,90)
        for name,request,winner in cases():
            request=parse_request(canonical(request));before=canonical(request)
            native,receipt=run_native('metamo',request,args.admission,outer_deadline=deadline)
            receipts.append(receipt)
            expected=[score(request['state'],candidate) for candidate in request['candidates']]
            actual=[row['score'] for row in native['scores']]
            if not all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9) for a,b in zip(actual,expected)):
                raise ValueError('Independent score oracle failed: '+name)
            if native['selected_proposal_id']!=winner or canonical(request)!=before:
                raise ValueError('Selection or fixed input state failed: '+name)
            checks.append({'name':name,'passed':True,'native_scores':actual,'oracle_scores':expected,'native_winner':winner})
        verify_inputs(args.admission,deadline-1)
        result.update(status='passed',inputs_unchanged=True,posthash_status='completed-unchanged')
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error))
        if hasattr(error,'receipt'): receipts.append(error.receipt)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        result['seconds']=time.monotonic()-started
        if result['seconds']>90:result.update(status='failed',error='Outer90s budget exceeded')
        payload=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode()
        if len(payload)>1024**2:raise ValueError('Receipt1MiB cap')
        with out.open('xb') as stream: stream.write(payload)
        print(json.dumps({'status':result.get('status'),'receipt':str(out),'sha256':hashlib.sha256(payload).hexdigest(),
                          'native_calls':len(receipts),'checks':len(checks),'seconds':result['seconds']}),flush=True)
    if result['status']!='passed':raise RuntimeError(result.get('error','Gate failed'))

if __name__=='__main__':main()
