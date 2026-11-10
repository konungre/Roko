#!/usr/bin/env python3
"""Read native private profiles, compare adapters without path normalization.

No profile switch, rollback, install, or package mutation is performed.
"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from qualify_planner_parity import WORKER

def qualify(repository,base,output):
 repository,base,output=map(lambda x:Path(x).resolve(),(repository,base,output));output.mkdir(mode=0o700)
 root=base/'atomic-profiles-001';active=root/'active';journal=root/'pointer.json'
 before={'pointer':os.readlink(active),'journal_sha256':hashlib.sha256(journal.read_bytes()).hexdigest() if journal.exists() else None}
 profiles=sorted(root.glob('generation-*/profile'));rows=[]
 nix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline']
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu'),'PYTHONDONTWRITEBYTECODE':'1'}
 observations=[]
 for p in profiles:
  r=subprocess.run(nix+['profile','list','--profile',str(p),'--json'],capture_output=True,text=True,env=env,timeout=30)
  if r.returncode:raise RuntimeError(r.stderr)
  manifest=json.loads(r.stdout);packages={name:element['storePaths'][0] for name,element in manifest['elements'].items()}
  if not packages:continue
  observations.append({'profile':str(p),'manifest':manifest,'raw_sha256':hashlib.sha256(r.stdout.encode()).hexdigest()})
  path=next(iter(packages.values()))
  snapshot={'packages':packages,'revision':hashlib.sha256(r.stdout.encode()).hexdigest(),'source':'native-private-profile:'+str(p)}
  cases={'native-workspace-paths':{'name':'roko','path':path,'snapshot':json.dumps(snapshot)},'canonical-desired-native-observed':{'name':'roko','path':'/nix/store/'+'0'*32+'-explicit-fixture','snapshot':json.dumps(snapshot)},'duplicate-provenance':{'name':'roko','path':'/nix/store/'+'0'*32+'-explicit-fixture','snapshot':'{"packages":{},"revision":"1","revision":"2","source":"fixture"}'}}
  for label,request in cases.items():
   pair=[]
   for module in ('package_planning','package_planning_v2'):
    result=subprocess.run([sys.executable,'-B','-c',WORKER,str(repository/'omega-baseline/adapters'),module],input=json.dumps(request),capture_output=True,text=True,timeout=10,env=env)
    if result.returncode:raise RuntimeError(result.stderr)
    pair.append(json.loads(result.stdout))
   # Exact rejection is required: do not rewrite real workspace paths to pretend
   # this is a canonical /nix/store installation.
   passed=all(not x['accepted'] for x in pair)
   rows.append({'profile':str(p),'case':label,'passed':passed,'legacy':pair[0],'successor':pair[1]})
 # A real retained empty native generation supports a successful plan fixture.
 empty=base/'profile-2-link'
 native=subprocess.run(nix+['profile','list','--profile',str(empty),'--json'],capture_output=True,text=True,env=env,timeout=30)
 if native.returncode:raise RuntimeError(native.stderr)
 manifest=json.loads(native.stdout)
 if manifest['elements']:raise ValueError('expected retained empty fixture generation')
 observations.append({'profile':str(empty),'manifest':manifest,'raw_sha256':hashlib.sha256(native.stdout.encode()).hexdigest()})
 request={'name':'fixture','path':'/nix/store/'+'0'*32+'-explicit-fixture','snapshot':json.dumps({'packages':{},'revision':hashlib.sha256(native.stdout.encode()).hexdigest(),'source':'native-empty-profile:'+str(empty)})}
 pair=[]
 for module in ('package_planning','package_planning_v2'):
  result=subprocess.run([sys.executable,'-B','-c',WORKER,str(repository/'omega-baseline/adapters'),module],input=json.dumps(request),capture_output=True,text=True,timeout=10,env=env)
  if result.returncode:raise RuntimeError(result.stderr)
  pair.append(json.loads(result.stdout))
 passed=all(x['accepted'] and not x['authority'] and x['executed']==0 for x in pair) and pair[0]['complete_plan']==pair[1]['complete_plan']
 rows.append({'profile':str(empty),'case':'real-empty-profile-explicit-fixture-intent','passed':passed,'legacy':pair[0],'successor':pair[1]})
 missing=output/'missing-profile'
 failed=subprocess.run(nix+['path-info',str(missing)],capture_output=True,text=True,env=env,timeout=30)
 after={'pointer':os.readlink(active),'journal_sha256':hashlib.sha256(journal.read_bytes()).hexdigest() if journal.exists() else None}
 retained=all(p.exists() for p in profiles)
 report={'passed':bool(rows) and all(x['passed'] for x in rows) and failed.returncode!=0 and before==after and retained,'observations':observations,'comparisons':rows,'failed_read':{'returncode':failed.returncode,'stderr':failed.stderr},'pointer_unchanged':before==after,'retained_rollback_profiles_present':retained,'desired_paths_are_fixtures':True,'before':before,'after':after,'paths_rewritten':False,'package_mutations':0,'license_clearance':False,'scope':'real workspace-profile observations rejected by both canonical-path snapshot bridges; no installed /nix/store profile claim'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.output);print(json.dumps({'passed':r['passed'],'profiles':len(r['observations']),'cases':len(r['comparisons'])}));sys.exit(0 if r['passed'] else 1)
