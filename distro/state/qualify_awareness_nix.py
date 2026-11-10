"""Read retained disposable Nix profiles into native Hyperon; no profile writes."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
WORKER=r'''
import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from hyperon import MeTTa,Environment
import hyperon
from package_profile_observation_v2 import ReadOnlyProfile
from package_awareness_v2 import SnapshotAwareness
from package_awareness_store_v2 import AwarenessStore
assert hyperon.__version__=='0.2.10'
base,output=Path(sys.argv[2]),Path(sys.argv[3])
command=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline']
env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
def factory():return MeTTa(env_builder=Environment.custom_env(config_dir=None,create_config=False))
empty=base/'profile-2-link';populated=next((base/'atomic-profiles-001').glob('generation-*/profile'))
def fingerprint(profile):
 return {'link':os.readlink(profile),'manifest':hashlib.sha256((profile/'manifest.json').read_bytes()).hexdigest()}
before={str(p):fingerprint(p) for p in (empty,populated)}
backend=ReadOnlyProfile(command,empty,env);store=AwarenessStore(output/'checkpoint');awareness=SnapshotAwareness(backend,factory,store)
if sys.argv[4]=='write':
 first=awareness.refresh();assert first.snapshot.packages=={} and len(first.runtime.space().get_atoms())==2
 assert first.origin=='backend-observation' and first.token[2]==1 and backend.calls==1
 native_receipt=backend.last_receipt
 # Missing profile is an error, never a synthesized empty observation.
 broken=ReadOnlyProfile(command,output/'missing-profile',env);awareness.backend=broken
 try:awareness.refresh()
 except (ValueError,FileNotFoundError):pass
 else:raise AssertionError('missing profile accepted')
 assert awareness.current is first
 # Retain real workspace paths: unsupported paths fail before checkpoint publish.
 populated_backend=ReadOnlyProfile(command,populated,env);other=SnapshotAwareness(populated_backend,factory)
 try:other.refresh()
 except ValueError as error:
  assert str(error)=='store output';rejected=True
 else:raise AssertionError('workspace store paths accepted')
 assert other.current is None and populated_backend.last_receipt['native']['elements']
 result={'native_receipt':native_receipt,'unsupported_populated_receipt':populated_backend.last_receipt,'populated_rejected_without_rewrite':rejected,'missing_profile_preserved_current':True,'version':first.token[2]}
else:
 restored=awareness.restore();assert backend.calls==0 and restored.origin=='restored-historical-checkpoint'
 assert restored.snapshot.packages=={} and restored.token[2]==1
 refreshed=awareness.refresh();assert backend.calls==1 and refreshed.token[2]==2
 assert refreshed.snapshot.revision==restored.snapshot.revision and refreshed.origin=='backend-observation'
 result={'restored_origin':restored.origin,'restore_backend_calls':0,'new_backend_calls':backend.calls,'new_version':refreshed.token[2],'native_revision_unchanged':True,'native_receipt':backend.last_receipt}
after={str(p):fingerprint(p) for p in (empty,populated)};assert before==after
result.update(profiles_unchanged=True,legacy_imported='omega_pm.core' in sys.modules,authorizes_actions=False)
assert not result['legacy_imported'];store.close();print(json.dumps(result))
'''
def qualify(repository,base,output):
 repository,base,output=[Path(p).resolve() for p in (repository,base,output)];output.mkdir(mode=0o700);rows=[]
 for mode in ('write','restore-refresh'):
  run=subprocess.run([sys.executable,'-B','-c',WORKER,str(repository/'omega-baseline/adapters'),str(base),str(output),mode],capture_output=True,text=True,timeout=60,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  (output/(mode+'.stdout')).write_text(run.stdout);(output/(mode+'.stderr')).write_text(run.stderr)
  if run.returncode:raise RuntimeError(mode+': '+run.stderr)
  rows.append(json.loads(run.stdout))
 binary=base/'root/usr/bin/nix'
 version=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=10,env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')})
 if version.returncode:raise RuntimeError(version.stderr)
 report={'nix_version':version.stdout.strip(),'nix_executable_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'observer_sha256':hashlib.sha256((repository/'omega-baseline/adapters/package_profile_observation_v2.py').read_bytes()).hexdigest(),'passed':True,'native_hyperon_tested':True,'native_nix_profile_observed':True,'successful_profile':'real retained empty disposable profile','nonempty_workspace_profile':'rejected without rewriting','fresh_processes':2,'results':rows,'profile_mutations':0,'host_activation':False,'license_clearance':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('output');a=p.parse_args();print(json.dumps(qualify(a.repository,a.base,a.output)))
