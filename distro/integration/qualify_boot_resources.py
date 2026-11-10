"""Bounded low-memory/recovery fixtures; no allocations, VM or service activation."""
import argparse,contextlib,io,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nix'))
from startup_report import run
def qualify(output):
 output=Path(output).resolve();output.mkdir(mode=0o700);policy=output/'policy.json';boot=output/'boot-id';status=output/'status.json';meminfo=output/'meminfo'
 policy.write_text(json.dumps({'schema':'roko-first-boot-policy-v1','offlineRequested':True,'networkIsolationProven':False,'automaticUpgrade':False,'automaticGenerationDeletion':False,'modelReady':False,'durableHistoryReady':False,'credentialProvisioningRequired':True}));boot.write_text('00000000-0000-0000-0000-000000000001');meminfo.write_text('MemAvailable: 16000000 kB\n');(output/'memory.max').write_text(str(16*1024**3))
 rows=[]
 for name,current,expected in [('low',str(16*1024**3-128*1024**2),'headroom-low'),('invalid','private-fixture-invalid-input','unknown'),('recovered',str(2*1024**3),'resource-check-only-passed')]:
  (output/'memory.current').write_text(current);logs=io.StringIO()
  with contextlib.redirect_stdout(logs):code=run(policy,status,boot,meminfo=meminfo,cgroup=output)
  report=json.loads(status.read_text());(output/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n');(output/(name+'.stdout')).write_text(logs.getvalue())
  assert code==0 and report['status']=='unqualified' and not report['system_ready'] and not report['execution_authorized'] and report['resources']['status']==expected
  assert 'private-fixture-invalid-input' not in logs.getvalue()+status.read_text()
  rows.append({'case':name,'exit_code':code,'resource_status':report['resources']['status'],'system_ready':False})
 # Read the actual current budget with fixture policy/boot identity; not a boot test.
 with contextlib.redirect_stdout(io.StringIO()):assert run(policy,status,boot)==0
 actual=json.loads(status.read_text());(output/'current-resource-sample.json').write_text(json.dumps(actual,indent=2)+'\n')
 result={'passed':True,'cases':rows,'actual_resource_sample_status':actual['resources']['status'],'scope':'program fixture transitions and passive current memory sample; not systemd or guest boot','guest_started':False,'host_activation':False,'model_started':False,'system_ready':False}
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output');args=p.parse_args();print(json.dumps(qualify(args.output)))
