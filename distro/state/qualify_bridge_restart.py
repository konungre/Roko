"""Disposable bridge lifecycle; startup failure never silently falls back."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
WORKER=r'''
import builtins,json,sys
if sys.argv[2]=='missing-successor':
 original=builtins.__import__
 def fail(name,*a,**k):
  if name=='package_planning_v2':raise ModuleNotFoundError('injected successor unavailable')
  return original(name,*a,**k)
 builtins.__import__=fail
sys.path.insert(0,sys.argv[1])
try:
 import package_bridge as bridge
 request=json.load(sys.stdin)
 report=json.loads(bridge.plan_single(request['name'],request['path'],request['snapshot']))
 print(json.dumps({'started':True,'mode':bridge.PLANNER_MODE,'report':report,'legacy_imported':'omega_pm.core' in sys.modules}))
except (ValueError,ModuleNotFoundError) as error:
 print(json.dumps({'started':False,'error':str(error),'legacy_imported':'omega_pm.core' in sys.modules}))
'''
def qualify(repository,base,output):
 repository,base,output=map(lambda x:Path(x).resolve(),(repository,base,output));output.mkdir(mode=0o700)
 pointer=base/'profile';retained=sorted(base.glob('profile-*-link'))
 before={'profile':os.readlink(pointer),'retained':{str(p):os.readlink(p) for p in retained}}
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu'),'PYTHONDONTWRITEBYTECODE':'1'}
 nix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline']
 raw=subprocess.run(nix+['profile','list','--profile',str(base/'profile-2-link'),'--json'],env=env,capture_output=True,text=True,timeout=30)
 if raw.returncode:raise RuntimeError(raw.stderr)
 manifest=json.loads(raw.stdout)
 if manifest['elements']:raise ValueError('expected retained empty generation')
 request={'name':'fixture','path':'/nix/store/'+'0'*32+'-explicit-fixture','snapshot':json.dumps({'packages':{},'revision':hashlib.sha256(raw.stdout.encode()).hexdigest(),'source':'native-empty-profile:'+str(base/'profile-2-link')})}
 rows=[]
 for label,mode,fault in [('initial-default',None,'none'),('opt-in','successor-v2','none'),('missing-startup','successor-v2','missing-successor'),('invalid-startup','unknown','none'),('restored-default',None,'none')]:
  child_env=env.copy();child_env.pop('ROKO_PACKAGE_PLANNER',None)
  if mode is not None:child_env['ROKO_PACKAGE_PLANNER']=mode
  proc=subprocess.run([sys.executable,'-B','-c',WORKER,str(repository/'omega-baseline/integration'),fault],env=child_env,input=json.dumps(request),capture_output=True,text=True,timeout=10)
  if proc.returncode:raise RuntimeError(proc.stderr)
  result=json.loads(proc.stdout);rows.append({'phase':label,'result':result})
 old,new,missing,invalid,restored=[r['result'] for r in rows]
 complete=old['report']['plan']==new['report']['plan']==restored['report']['plan']
 after={'profile':os.readlink(pointer),'retained':{str(p):os.readlink(p) for p in retained}}
 passed=old['started'] and old['mode']=='legacy' and new['started'] and not new['legacy_imported'] and not missing['started'] and not missing['legacy_imported'] and not invalid['started'] and not invalid['legacy_imported'] and restored['started'] and restored['mode']=='legacy' and restored['report']==old['report'] and complete and before==after
 report={'passed':passed,'native_observation':manifest,'phases':rows,'complete_plans_equal':complete,'profile_and_rollback_links_unchanged':before==after,'before':before,'after':after,'desired_path_is_fixture':True,'host_activation':False,'license_clearance':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.output);print(json.dumps({'passed':r['passed'],'phases':len(r['phases'])}));sys.exit(0 if r['passed'] else 1)
