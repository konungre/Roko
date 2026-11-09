"""Bounded native diagnostic negative controls; never starts a real model load."""
import argparse,hashlib,json,os,resource,subprocess,time
from pathlib import Path
from memory_budget import observe,admit
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(5,5));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def qualify(executable,output):
 executable=Path(executable).resolve(strict=True);output=Path(output).resolve();output.mkdir(mode=0o700);rows=[]
 for label,args,expected in [('argument-rejection',[],2),('missing-model',['load',str(output/'absent.gguf')],3)]:
  started=time.monotonic();run=subprocess.run([str(executable),*args],capture_output=True,text=True,timeout=10,preexec_fn=limits)
  (output/(label+'.stdout')).write_text(run.stdout);(output/(label+'.stderr')).write_text(run.stderr)
  phases=[json.loads(line.split(' ',1)[1]) for line in run.stderr.splitlines() if line.startswith('ROKO_INFERENCE_PHASE ')]
  names=[row['phase'] for row in phases];expected_names=['entered'] if label=='argument-rejection' else ['entered','backend-begin','backend-end','model-load-begin']
  passed=run.returncode==expected and names==expected_names and all(row['uid']==os.getuid() for row in phases) and [row['elapsed_ms'] for row in phases]==sorted(row['elapsed_ms'] for row in phases)
  rows.append({'case':label,'returncode':run.returncode,'passed':passed,'wall_seconds':time.monotonic()-started,'phases':phases})
 memory=observe()
 try:admit(512,observation=memory);memory['new_512mib_guest_admitted']=True
 except ValueError:memory['new_512mib_guest_admitted']=False
 report={'passed':all(row['passed'] for row in rows),'cases':rows,'memory':memory,'binary_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),'probe_source_sha256':hashlib.sha256(Path(__file__).with_name('inference_phase_probe.cpp').read_bytes()).hexdigest(),'real_model_loaded':False,'inference_completed':False,'guest_started':False,'host_activation':False,'scope':'host native argument/missing-model negative controls and current memory admission observation'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('executable');p.add_argument('output');a=p.parse_args();r=qualify(a.executable,a.output);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
