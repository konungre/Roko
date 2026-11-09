"""Finite real Roko controller exercise inside the guest, with no model or autonomy."""
import json,subprocess,sys
CLI='/opt/roko/scripts/roko.py'
BASE=[sys.executable,CLI,'--state-dir','/var/lib/roko']
def run(*args,expected=0):
 result=subprocess.run([*BASE,*args],capture_output=True,text=True,timeout=15)
 if result.returncode!=expected:
  print(result.stdout);print(result.stderr);raise RuntimeError('Guest command failed: '+str(args))
 return result.stdout
run('create','guest-arithmetic','--goal','Verify guest checkpoint recovery')
run('evidence','guest-arithmetic','source','--source','fixture:guest','--text','Arithmetic: 7 * 8.')
run('propose','guest-arithmetic','--tool','record_answer','--arguments','{"text":"55"}','--evidence','source')
run('check','guest-arithmetic','--checker','arithmetic')
run('close','guest-arithmetic',expected=2)
rejected=json.loads(run('show','guest-arithmetic'))
assert rejected['state']['phase']=='open'
print('ROKO_GUEST_REJECTION_PASSED',flush=True)
run('propose','guest-arithmetic','--tool','record_answer','--arguments','{"text":"56"}','--evidence','source')
run('check','guest-arithmetic','--checker','arithmetic')
run('close','guest-arithmetic')
recovered=json.loads(run('show','guest-arithmetic'))
assert recovered['state']['phase']=='closed'
assert recovered['state']['verification']['authorizes_actions'] is False
assert recovered['state']['executed_actions']==0
print('ROKO_GUEST_STATE '+json.dumps(recovered,sort_keys=True),flush=True)
run('create','guest-no-model','--goal','Missing model must fail closed')
run('evidence','guest-no-model','source','--source','fixture:guest','--text','ready')
run('infer','guest-no-model','--tool','record_answer','--evidence','source','--prompt','Repeat the evidence',expected=2)
unavailable=json.loads(run('show','guest-no-model'))
assert unavailable['state']['phase']=='open' and unavailable['state']['proposal'] is None
print('ROKO_GUEST_MODEL_FAIL_CLOSED',flush=True)
petta=subprocess.run(['/bin/sh','/bin/petta-smoke'],capture_output=True,text=True,timeout=35)
print(petta.stdout,flush=True)
if petta.returncode:
 print(petta.stderr,flush=True);raise RuntimeError('Guest PeTTa/Janus check failed')
assert 'ROKO_GUEST_PETTA_ARITHMETIC_PASSED result=56' in petta.stdout
assert 'ROKO_GUEST_JANUS_PASSED result=42' in petta.stdout
print('ROKO_GUEST_CONTROLLER_PASSED',flush=True)
