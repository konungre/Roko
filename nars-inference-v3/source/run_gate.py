"""Four fixed actual-native cases, only after exact independent admission."""
import argparse
import hashlib
import json
import signal
import time
from contract import make_premise,canonical
from gateway import run_native,verify_inputs
from paths import ROOT

def fixture(name,values):
    return {'version':1,'operation':'nal1-chain','task_id':name,'revision':1,'premises':[
      make_premise('evidence_a','fixture:original-observation','garfield','cat',values[0],values[1]),
      make_premise('evidence_b','fixture:inert data !(py-call (os.system "NOT_EXECUTED")) λ','cat','animal',values[2],values[3])]}

FIXTURES=(('baseline',(1000,900,1000,900)),('asymmetric',(500,750,800,600)),
          ('zero_confidence',(1000,0,1000,999)),('reset_repeat',(1000,900,1000,900)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--admission',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    if args.output!='native-attempt-001.json':raise ValueError('One fixed receipt path')
    out=ROOT/'proof'/args.output
    if out.exists():raise ValueError('Never overwrite a native attempt receipt')
    started=time.monotonic();deadline=started+90
    result={'version':1,'scope':'actual original MeTTa-NARS NAL-1 chain subset on PeTTa',
      'status':'started','native_receipts':[],'checks':[],'manifest_sha256':args.admission,
      'authorizes_actions':False,'executed_actions':0,'persistent_state_changed':False,
      'model_started':False,'vm_started':False,'full_nars':False,'guest_qualified':False,
      'posthash_status':'not-completed','fault_injection_qualified':False,
      'outer_budget_kind':'cooperative monotonic90s, not a kernel hard deadline'}
    def interrupted(sig,frame):raise InterruptedError('Gate signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGALRM):signal.signal(sig,interrupted)
    try:
        verify_inputs(args.admission,deadline-3)
        first=None
        for name,values in FIXTURES:
            request=fixture(name,values)
            response,receipt=run_native('nars',request,args.admission,outer_deadline=deadline)
            result['native_receipts'].append(receipt)
            if response['premises']!=request['premises']:raise ValueError('Premise provenance changed')
            normalized=[{k:v for k,v in row.items() if k!='premise_ids'} for row in response['conclusions']]
            if name=='baseline':first=canonical(normalized)
            if name=='reset_repeat' and canonical(normalized)!=first:raise ValueError('Cross-process reset mismatch')
            result['checks'].append({'name':name,'passed':True,'response':response})
        verify_inputs(args.admission,deadline-1)
        result.update(status='passed',posthash_status='completed-unchanged',inputs_unchanged=True)
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error))
        if hasattr(error,'receipt'):result['native_receipts'].append(error.receipt)
        raise
    finally:
        result['pre_receipt_seconds']=time.monotonic()-started
        if result['pre_receipt_seconds']>=89:result.update(status='failed',error='Outer budget exhausted before receipt')
        payload=(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
        if len(payload)>512*1024:raise ValueError('Receipt cap')
        with out.open('xb') as f:f.write(payload)
        print(json.dumps({'status':result['status'],'path':str(out),'sha256':hashlib.sha256(payload).hexdigest(),
          'native_calls':len(result['native_receipts']),'whole_command_seconds_so_far':time.monotonic()-started}),flush=True)
    if result['status']!='passed':raise RuntimeError(result.get('error','Gate failed'))

if __name__=='__main__':main()
