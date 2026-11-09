"""Exact two-process native→proposal→detached-checker gate. Admission required."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import stat
import sys
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CORE=ROOT.parent/'metamo-core-v4'
sys.path.insert(0,str(CORE/'source'))
from gateway import verify_inputs,run_native
from proposal_adapter import EXPECTED_MANIFEST,score_and_offer,preview_check
from metamo_contract import canonical
from qualified_fixtures import cases

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_adapter(admission,deadline):
    if time.monotonic()>=deadline:raise TimeoutError('Adapter deadline')
    p=ROOT/'proof/adapter-inputs.json'
    if sha(p)!=admission:raise ValueError('Exact adapter manifest required')
    lock=json.loads(p.read_bytes())
    if lock['source_tree']!=str(HERE) or [str(p.relative_to(HERE)) for p in sorted(HERE.rglob('*'))]!=lock['tree_entries']:
        raise ValueError('Adapter source membership')
    for name,row in lock['files'].items():
        if time.monotonic()>=deadline:raise TimeoutError('Adapter hash deadline')
        p=Path(name)
        if p.resolve()!=p or not p.is_file() or p.stat().st_size!=row['bytes'] or stat.S_IMODE(p.stat().st_mode)!=row['mode'] or sha(p)!=row['sha256']:
            raise ValueError('Adapter source changed')
    if lock['core_manifest_sha256']!=EXPECTED_MANIFEST:raise ValueError('Core identity changed')
    verify_inputs(EXPECTED_MANIFEST,deadline)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--admission',required=True);args=parser.parse_args()
    proof=ROOT/'proof';marker=proof/'native-started-001.json';out=proof/'native-attempt-001.json'
    if marker.exists() or out.exists():raise ValueError('Attempt already consumed; no retry')
    start=time.monotonic();deadline=start+60;receipts=[];checks=[]
    def interrupted(number,frame):raise InterruptedError('Adapter gate signal '+str(number))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGALRM):signal.signal(sig,interrupted)
    result={'version':1,'scope':'two real MAGUS selections to existing controller proposal/verification contract',
            'adapter_manifest_sha256':args.admission,'core_manifest_sha256':EXPECTED_MANIFEST,
            'native_receipts':receipts,'checks':checks,'posthash_status':'not-completed',
            'model_started':False,'VM_started':False,'guest_tested':False,'full_metamo_cycle_tested':False,
            'persistent_state_changed':False,'executed_actions':0,'authorizes_actions':False,
            'outer_budget_kind':'cooperative60s plus one-shot60s signal; no hard blocked-filesystem interruption'}
    try:
        verify_adapter(args.admission,deadline-3)
        with marker.open('x') as stream:json.dump({'admission':args.admission,'maximum_native_processes':2},stream)
        signal.setitimer(signal.ITIMER_REAL,60)
        def run(kind,request):
            if len(receipts)>=2:raise ValueError('Native call count cap')
            response,receipt=run_native(kind,request,EXPECTED_MANIFEST,outer_deadline=deadline)
            receipts.append(receipt);return response,receipt
        for name,state,plan,expected in cases():
            original=canonical(state.snapshot())
            advice=score_and_offer(plan,run=run,current=lambda:(state.snapshot(),1))
            checked=preview_check(plan,advice,'integer-arithmetic-v1')
            if advice['proposal_id']!='high' or checked['verification']['accepted'] is not expected:
                raise ValueError('Real native selection or deterministic verification differs: '+name)
            if canonical(state.snapshot())!=original or state.snapshot()['phase']!='open':
                raise ValueError('Original state changed')
            if advice['executed_actions']!=0 or checked['executed_actions']!=0 or checked['task_closed'] or checked['persistent_state_changed']:
                raise ValueError('Authority changed')
            checks.append({'name':name,'passed':True,'native_selected_proposal':advice['proposal_id'],
                           'native_proposal':advice['proposal'],'native_scores':advice['scores'],
                           'independent_verification':checked['verification'],'original_state_unchanged':True,
                           'original_evidence_count':len(state.snapshot()['evidence']),'original_phase':'open',
                           'advice':advice,'preview':checked})
        verify_adapter(args.admission,deadline-1)
        result.update(status='passed',inputs_unchanged=True,posthash_status='completed-unchanged')
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error))
        if hasattr(error,'receipt'):receipts.append(error.receipt)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        result['seconds']=time.monotonic()-start
        if result['seconds']>60:result.update(status='failed',error='Whole60s budget exceeded')
        payload=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode()
        if len(payload)>1024**2:raise ValueError('Receipt1MiB cap')
        with out.open('xb') as stream:stream.write(payload)
        print(json.dumps({'status':result.get('status'),'native_calls':len(receipts),'checks':len(checks),
                          'seconds':result['seconds'],'receipt_sha256':hashlib.sha256(payload).hexdigest()}),flush=True)
    if result['status']!='passed':raise RuntimeError(result.get('error','Adapter qualification failed'))

if __name__=='__main__':main()
