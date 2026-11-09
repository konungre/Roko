"""Fresh-process packaged-program fixture transitions under explicit rlimits."""
import argparse,hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
WORKER=r'''
import json,sys,resource,os
from pathlib import Path
package=Path(sys.argv[1]);sys.path.insert(0,str(package))
import startup_report,memory_budget
assert Path(startup_report.__file__).parent==package and Path(memory_budget.__file__).parent==package
root=Path(sys.argv[2]);code=startup_report.run(root/'policy.json',root/'status.json',root/'boot-id',meminfo=root/'meminfo',cgroup=root)
print('ROKO_PROCESS_RESOURCE '+json.dumps({'exit_code':code,'pid':os.getpid(),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'isolated_package_imports':True}));raise SystemExit(code)
'''
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(96*1024**2,96*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(2,2));resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NOFILE,(32,32));resource.setrlimit(resource.RLIMIT_FSIZE,(65536,65536))
def qualify(output):
 output=Path(output).resolve();output.mkdir(mode=0o700);package=output/'package';package.mkdir();source=Path(__file__).resolve().parents[1]/'nix';hashes={}
 for name in ('startup_report.py','memory_budget.py'):
  shutil.copy2(source/name,package/name);hashes[name]=hashlib.sha256((package/name).read_bytes()).hexdigest()
 (output/'policy.json').write_text(json.dumps({'schema':'roko-first-boot-policy-v1','offlineRequested':True,'networkIsolationProven':False,'automaticUpgrade':False,'automaticGenerationDeletion':False,'modelReady':False,'durableHistoryReady':False,'credentialProvisioningRequired':True}))
 boot1='00000000-0000-0000-0000-000000000001';boot2='00000000-0000-0000-0000-000000000002';limit=16*1024**3;threshold=6*1024**3
 cases=[('low',limit-128*1024**2,'MemAvailable: 16000000 kB\n','headroom-low',boot1),('wrong-unit',0,'MemAvailable: 16000000 MB\n','unknown',boot1),('duplicate',0,'MemAvailable: 16000000 kB\nMemAvailable: 16000000 kB\n','unknown',boot1),('one-byte-below',limit-threshold+1,'MemAvailable: 16000000 kB\n','headroom-low',boot1),('exact-threshold',limit-threshold,'MemAvailable: 16000000 kB\n','resource-check-only-passed',boot1),('new-boot-low',limit-128*1024**2,'MemAvailable: 16000000 kB\n','headroom-low',boot2)]
 (output/'memory.max').write_text(str(limit));rows=[];previous_time=0
 for name,current,meminfo,expected,boot in cases:
  (output/'memory.current').write_text(str(current));(output/'meminfo').write_text(meminfo);(output/'boot-id').write_text(boot)
  run=subprocess.run([sys.executable,'-I','-B','-c',WORKER,str(package),str(output)],capture_output=True,text=True,timeout=5,preexec_fn=limits)
  (output/(name+'.stdout')).write_text(run.stdout);(output/(name+'.stderr')).write_text(run.stderr)
  if run.returncode:raise RuntimeError(name+': '+run.stderr)
  report=json.loads((output/'status.json').read_text());meta=json.loads(next(line.split(' ',1)[1] for line in run.stdout.splitlines() if line.startswith('ROKO_PROCESS_RESOURCE ')))
  assert report['resources']['status']==expected and report['status']=='unqualified' and report['system_ready'] is False and report['execution_authorized'] is False and report['boot_id']==boot
  assert (output/'status.json').stat().st_mode&0o777==0o640 and not list(output.glob('.startup-*'))
  if 'sampled_monotonic_ns' in report['resources']:
   assert report['resources']['sampled_monotonic_ns']>previous_time;previous_time=report['resources']['sampled_monotonic_ns']
  (output/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n');rows.append({'case':name,'expected':expected,'boot_id':boot,'process':meta})
 assert all(hashlib.sha256((package/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items())
 result={'passed':True,'cases':rows,'package_hashes':hashes,'limits':{'address_space_mib':96,'cpu_seconds':2,'wall_seconds_per_process':5,'fd_limit':32,'file_size_bytes':65536},'scope':'isolated copy matching two-file layout, not a realized Nix derivation or systemd cgroup test','guest_started':False,'model_started':False,'host_activation':False,'system_ready':False}
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();r=qualify(a.output);print(json.dumps({'passed':r['passed'],'fresh_processes':len(r['cases'])}))
