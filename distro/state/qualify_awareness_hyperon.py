"""Explicit native host qualification; not part of dependency-free fixture tests."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
WORKER = r'''
import json,sys,threading
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
import hyperon
from hyperon import MeTTa,Environment
from package_awareness_v2 import SnapshotAwareness
from package_awareness_store_v2 import AwarenessStore
assert hyperon.__version__=='0.2.10'
def factory():return MeTTa(env_builder=Environment.custom_env(config_dir=None,create_config=False))
class Backend:
 identity='native-read-only-fixture'
 def __init__(self):self.packages={'hello':'/nix/store/'+'0'*32+'-fixture'};self.revision='1';self.calls=0
 def observe(self):self.calls+=1;return SimpleNamespace(packages=dict(self.packages),revision=self.revision)
def atoms(observation):return [str(x) for x in observation.runtime.space().get_atoms()]
def installed(observation):
 return list(observation.runtime.space().query(list(observation.runtime.parse_all('(installed $name $path)'))[0]).iterator())
b=Backend();store=AwarenessStore(sys.argv[2]);a=SnapshotAwareness(b,factory,store)
if sys.argv[3]=='write':
 old=a.refresh();old_atoms=atoms(old)
 assert len(old_atoms)==3 and len(installed(old))==1
 b.packages={};b.revision='2';new=a.refresh()
 assert len(atoms(new))==2 and len(installed(new))==0
 assert atoms(old)==old_atoms and len(installed(old))==1
 def broken():raise RuntimeError('qualification failure')
 a.runtime_factory=broken
 try:a.refresh()
 except RuntimeError:pass
 else:raise AssertionError('failure not propagated')
 assert a.current is new and atoms(old)==old_atoms
 # Revision text remains a grounded string, never an executable top-level atom.
 b.revision='") !(exec "not-run")\n';a.runtime_factory=factory;escaped=a.refresh()
 rows=escaped.runtime.space().get_atoms();assert len(rows)==2
 revision_atoms=[atom for atom in rows if str(atom.get_children()[0])=='state-revision'];assert len(revision_atoms)==1
 children=revision_atoms[0].get_children()
 assert str(children[0])=='state-revision' and children[1].get_object().value==b.revision
 assert escaped.live_hyperon_verified is False # generic API does not self-attest
 # Native spaces also obey latest-started-wins when observations overlap.
 entered=threading.Event();release=threading.Event();errors=[]
 class ConcurrentBackend:
  identity='native-concurrent-fixture'
  def observe(self):
   if threading.current_thread().name=='old-observer':
    entered.set();assert release.wait(5);revision='old'
   else:revision='new'
   return SimpleNamespace(packages={},revision=revision)
 concurrent=SnapshotAwareness(ConcurrentBackend(),factory)
 def slow():
  try:concurrent.refresh()
  except Exception as error:errors.append(str(error))
 thread=threading.Thread(target=slow,name='old-observer');thread.start();assert entered.wait(5)
 newest=concurrent.refresh();release.set();thread.join(5)
 assert not thread.is_alive() and errors==['superseded refresh'] and concurrent.current is newest
 assert newest.snapshot.revision=='new' and len(atoms(newest))==2
 result={'initial_atoms':old_atoms,'removed_atoms':atoms(new),'escaped_atoms':atoms(escaped),'failed_refresh_preserved':True,'old_space_unchanged':True,'native_concurrent_refresh_rejected':True,'version':escaped.token[2]}
else:
 restored=a.restore();assert b.calls==0 and restored.origin=='restored-historical-checkpoint'
 assert len(atoms(restored))==2 and len(installed(restored))==0
 assert restored.token[2]==3 and not restored.authorizes_actions
 result={'restored_atoms':atoms(restored),'origin':restored.origin,'version':restored.token[2],'backend_calls':b.calls}
result.update(hyperon_version=hyperon.__version__,legacy_imported='omega_pm.core' in sys.modules,authorizes_actions=False)
assert not result['legacy_imported'];store.close();print(json.dumps(result))
'''
def qualify(repository, output):
 root=Path(repository).resolve();output=Path(output).resolve();output.mkdir(mode=0o700)
 rows=[]
 for mode in ('write','restore'):
  run=subprocess.run([sys.executable,'-B','-c',WORKER,str(root/'omega-baseline/adapters'),str(output/'checkpoint'),mode],capture_output=True,text=True,timeout=20,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  (output/(mode+'.stdout')).write_text(run.stdout);(output/(mode+'.stderr')).write_text(run.stderr)
  if run.returncode:raise RuntimeError(mode+': '+run.stderr)
  rows.append(json.loads(run.stdout))
 report={'passed':True,'native_hyperon_tested':True,'version':'0.2.10','backend':'read-only synthetic package observations','fresh_processes':2,'results':rows,'package_mutations':0,'host_activation':False,'license_clearance':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('repository');parser.add_argument('output');args=parser.parse_args()
 print(json.dumps(qualify(args.repository,args.output)))
