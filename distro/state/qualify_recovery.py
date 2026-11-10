"""Inject interrupted journal finalization in a disposable real Nix profile."""
import argparse,json,os
from pathlib import Path
from unittest.mock import patch
import profile_switch
from profile_switch import Profiles

def qualify(base,out,before_pointer=False):
 base=Path(base).resolve();out=Path(out).resolve();out.mkdir(mode=0o700)
 p=Profiles(out/'profiles',str(base/'root/usr/bin/nix'),'local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),{**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')})
 paths=[]
 for n in (1,2):
  paths.append(json.loads(p.run('--option','build-users-group','','--option','sandbox','false','build','--impure','--file',str(base/f'profile-{n}.nix'),'--no-link','--json'))[0]['outputs']['out'])
 first=p.switch({'roko':paths[0]},p.current(),True)
 original=profile_switch.save
 def fail_final(path,state):
  if not state['pending']:raise OSError('injected loss before journal finalization')
  original(path,state)
 original_replace=os.replace
 def fail_pointer(src,dst):
  if Path(dst).name=='active':raise OSError('injected loss before pointer rename')
  original_replace(src,dst)
 injection=patch('profile_switch.os.replace',fail_pointer) if before_pointer else patch('profile_switch.save',fail_final)
 try:
  with injection:p.switch({'roko':paths[1]},p.current(),True)
 except OSError:pass
 else:raise AssertionError('injection not reached')
 pending=json.loads((p.root/'pointer.json').read_text());actual=os.readlink(p.root/'active');assert pending['pending']
 try:p.current()
 except ValueError:blocked=True
 else:blocked=False
 try:p.recover(first['after']['target'],pending,actual,False)
 except PermissionError:unreviewed=True
 else:unreviewed=False
 result=p.recover(first['after']['target'],pending,actual,True)
 assert (p.root/'active/share/roko-generation').read_text()=='1'
 assert result['after']['revision']==3
 try:p.recover(first['after']['target'],pending,actual,True)
 except ValueError:replay=True
 else:replay=False
 report={'passed':blocked and unreviewed and replay,'injected_failure':'before pointer rename' if before_pointer else 'after pointer rename, before journal finalized','pending':pending,'actual_at_interruption':actual,'recovery':result,'blocked_while_pending':blocked,'unreviewed_rejected':unreviewed,'stale_recovery_rejected':replay,'host_activation':False}
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('output');p.add_argument('--before-pointer',action='store_true');a=p.parse_args();r=qualify(a.base,a.output,a.before_pointer);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
