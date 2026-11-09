"""Four fixed real AIRIS transition cases, only on separate exact admission."""
import argparse
import hashlib
import json
import signal
import time
from contract import observation,canonical
from gateway import run_native,verify_inputs
from paths import ROOT

def fixture(name,delta,query):
 rows=[]
 for i,(before,action) in enumerate(((2,'step'),(4,'step'),(2,'hold'),(4,'hold'))):
  rows.append(observation('evidence_'+str(i),'synthetic:recorded transition; inert __import__("os").system("NOT_EXECUTED") λ',before,action,before+(delta if action=='step' else 0)))
 return {'version':1,'operation':'learn-scalar-transition','task_id':name,'revision':1,'training':rows,'query':query}
FIXTURES=(('increment',1,7),('decrement',-1,7),('double_step',2,11),('reset_repeat',1,7))

def main():
 p=argparse.ArgumentParser();p.add_argument('--admission',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 if a.output!='native-attempt-001.json':raise ValueError('Fixed output only')
 out=ROOT/'proof'/a.output
 if out.exists():raise ValueError('Never overwrite an attempt')
 started=time.monotonic();deadline=started+90
 result={'version':1,'status':'started','scope':'original AIRIS bounded scalar transition learning/prediction subset','manifest_sha256':a.admission,'native_receipts':[],'checks':[],'posthash_status':'not-completed','authorizes_actions':False,'executed_external_actions':0,'persistent_state_changed':False,'model_started':False,'vm_started':False,'full_airis':False,'guest_qualified':False,'general_causal_learning_established':False,'fault_injection_qualified':False,'outer_budget_kind':'cooperative monotonic90s, not a kernel hard deadline'}
 def interrupted(sig,frame):raise InterruptedError('Gate signal '+str(sig))
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGALRM):signal.signal(sig,interrupted)
 try:
  verify_inputs(a.admission,deadline-3);first=None
  for name,delta,query in FIXTURES:
   req=fixture(name,delta,query);response,receipt=run_native('airis',req,a.admission,outer_deadline=deadline);result['native_receipts'].append(receipt)
   if name=='increment':first=canonical(response['predictions'])
   if name=='reset_repeat' and canonical(response['predictions'])!=first:raise ValueError('Fresh-process reset mismatch')
   result['checks'].append({'name':name,'passed':True,'response':response})
  verify_inputs(a.admission,deadline-1);result.update(status='passed',posthash_status='completed-unchanged',inputs_unchanged=True)
 except BaseException as e:
  result.update(status='failed',error=type(e).__name__+': '+str(e))
  if hasattr(e,'receipt'):result['native_receipts'].append(e.receipt)
  raise
 finally:
  result['pre_receipt_seconds']=time.monotonic()-started
  if result['pre_receipt_seconds']>=89:result.update(status='failed',error='Budget exhausted before receipt')
  payload=(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
  if len(payload)>512*1024:raise ValueError('Receipt cap')
  with out.open('xb') as f:f.write(payload)
  print(json.dumps({'status':result['status'],'sha256':hashlib.sha256(payload).hexdigest(),'native_calls':len(result['native_receipts']),'seconds_so_far':time.monotonic()-started}),flush=True)
 if result['status']!='passed':raise RuntimeError('Gate failed')
if __name__=='__main__':main()
