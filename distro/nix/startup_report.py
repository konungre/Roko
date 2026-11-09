"""Local startup diagnostics. Policy declarations never establish runtime health."""
import argparse,json,os,re,tempfile
from pathlib import Path
from memory_budget import observe
FIELDS={'offlineRequested','networkIsolationProven','automaticUpgrade','automaticGenerationDeletion','modelReady','durableHistoryReady','credentialProvisioningRequired'}
def inspect(policy,boot_id):
 if not isinstance(policy,dict) or set(policy)!=(FIELDS|{'schema'}) or policy['schema']!='roko-first-boot-policy-v1' or any(type(policy[k]) is not bool for k in FIELDS):raise ValueError('invalid-policy')
 if not isinstance(boot_id,str) or not re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',boot_id):raise ValueError('invalid-boot-identity')
 issues=['runtime-health-not-observed']
 for key,code in [('modelReady','model-not-qualified'),('durableHistoryReady','durable-history-not-qualified')]:
  if not policy[key]:issues.append(code)
 if policy['credentialProvisioningRequired']:issues.append('credentials-not-provisioned')
 if policy['offlineRequested'] and not policy['networkIsolationProven']:issues.append('network-isolation-not-proven')
 if policy['automaticUpgrade'] or policy['automaticGenerationDeletion']:issues.append('automatic-state-change-declared')
 return {'schema':'roko-startup-report-v1','boot_id':boot_id,'status':'unqualified','issues':issues,'declared_policy':policy,'runtime_health_observed':False,'system_ready':False,'execution_authorized':False,'scope':'boot-local policy diagnostics; no service/model/persistence probe'}
def write_report(output,report):
 output=Path(output);temporary=None
 try:
  fd,temporary=tempfile.mkstemp(prefix='.startup-',dir=output.parent)
  with os.fdopen(fd,'w') as stream:
   os.fchmod(stream.fileno(),0o640);json.dump(report,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,output);temporary=None
  fd=os.open(output.parent,os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 finally:
  if temporary is not None:os.unlink(temporary)
def resource_status(required_mib,meminfo,cgroup):
 if type(required_mib) is not int or not 512<=required_mib<=32768:raise ValueError('invalid model memory requirement')
 try:
  observation=observe(Path(meminfo),Path(cgroup));enough=observation['observed_headroom_bytes']>=required_mib*1024**2
  return {**observation,'status':'resource-check-only-passed' if enough else 'headroom-low','required_model_headroom_mib':required_mib,'model_start_recommendation':'resource-check-only-passed' if enough else 'defer','execution_authorized':False}
 except (OSError,ValueError,TypeError,StopIteration,IndexError):
  return {'status':'unknown','required_model_headroom_mib':required_mib,'model_start_recommendation':'defer','execution_authorized':False}
def run(policy_path,output,boot_id_path,*,required_headroom_mib=6144,meminfo='/proc/meminfo',cgroup='/sys/fs/cgroup'):
 try:
  with Path(policy_path).open('rb') as stream:raw=stream.read(65537)
  if len(raw)>65536:raise ValueError('policy-too-large')
  def unique(pairs):
   result={}
   for key,value in pairs:
    if key in result:raise ValueError('duplicate-policy-field')
    result[key]=value
   return result
  with Path(boot_id_path).open() as stream:boot_id=stream.read(256).strip()
  report=inspect(json.loads(raw,object_pairs_hook=unique),boot_id);code=0
  report['resources']=resource_status(required_headroom_mib,meminfo,cgroup)
  if report['resources']['status']=='headroom-low':report['issues'].append('optional-model-deferred-low-memory')
  elif report['resources']['status']=='unknown':report['issues'].append('memory-observation-unavailable')
 except (OSError,ValueError,TypeError):
  report={'schema':'roko-startup-report-v1','status':'failed','issues':['startup-policy-or-boot-identity-unreadable-or-invalid'],'runtime_health_observed':False,'system_ready':False,'execution_authorized':False};code=1
 write_report(output,report)
 print(json.dumps({'status':report['status'],'issues':report['issues'],'system_ready':False},sort_keys=True))
 return code
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--policy',required=True);parser.add_argument('--output',required=True);parser.add_argument('--model-required-headroom-mib',type=int,default=6144);parser.add_argument('--boot-id-file',default='/proc/sys/kernel/random/boot_id');args=parser.parse_args();raise SystemExit(run(args.policy,args.output,args.boot_id_file,required_headroom_mib=args.model_required_headroom_mib))
