"""Three-process fixture checkpoint recovery, not native Hyperon integration."""
import argparse,json,os,subprocess,sys
from pathlib import Path
WORKER=r'''
import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from package_awareness_v2 import SnapshotAwareness
from package_awareness_store_v2 import AwarenessStore
class Runtime:
 def __init__(self):self.atoms=[]
 def parse_all(self,s):return s.splitlines()
 def space(self):return self
 def add_atom(self,a):self.atoms.append(a)
class Backend:
 identity='read-only-restart-fixture'
 def __init__(self):self.calls=0;self.packages={'hello':'/nix/store/'+'0'*32+'-fixture'};self.revision='fixture-a'
 def observe(self):self.calls+=1;return SimpleNamespace(packages=dict(self.packages),revision=self.revision)
s=AwarenessStore(Path(sys.argv[2]));b=Backend();a=SnapshotAwareness(b,Runtime,s)
if sys.argv[3]=='write':
 value=a.refresh();result={'origin':value.origin,'token':value.token,'atoms':value.runtime.atoms,'backend_calls':b.calls}
elif sys.argv[3]=='restore-refresh':
 old=a.restore();calls_at_restore=b.calls;assert old.origin=='restored-historical-checkpoint' and calls_at_restore==0
 b.packages={};b.revision='fixture-b';value=a.refresh();assert not any(x.startswith('(installed ') for x in value.runtime.atoms)
 result={'restored_origin':old.origin,'restored_token':old.token,'backend_calls_at_restore':calls_at_restore,'origin':value.origin,'token':value.token,'atoms':value.runtime.atoms,'backend_calls':b.calls}
else:
 value=a.restore();assert value.snapshot.packages=={} and b.calls==0
 result={'origin':value.origin,'token':value.token,'atoms':value.runtime.atoms,'backend_calls':b.calls}
result['legacy_imported']='omega_pm.core' in sys.modules;result['authorizes_actions']=value.authorizes_actions;s.close();print(json.dumps(result))
'''
def qualify(repository,output):
 root=Path(repository).resolve();output=Path(output).resolve();output.mkdir(mode=0o700);rows=[]
 for mode in ('write','restore-refresh','restore-only'):
  p=subprocess.run([sys.executable,'-B','-c',WORKER,str(root/'omega-baseline/adapters'),str(output/'checkpoint'),mode],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=10)
  (output/(mode+'.stdout')).write_text(p.stdout);(output/(mode+'.stderr')).write_text(p.stderr)
  if p.returncode:raise RuntimeError(p.stderr)
  rows.append(json.loads(p.stdout))
 first,second,third=rows
 passed=first['token'][-1]==1 and second['token'][-1]==2 and third['token'][-1]==2 and len({r['token'][0] for r in rows})==3 and all(not r['legacy_imported'] and not r['authorizes_actions'] for r in rows) and third['origin']=='restored-historical-checkpoint' and third['backend_calls']==0
 report={'passed':passed,'process_results':rows,'native_hyperon_tested':False,'package_mutations':0,'host_activation':False,'scope':'private SQLite snapshot checkpoint and fixture spaces; no live owner subscription'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.output);print(json.dumps({'passed':r['passed'],'native_hyperon_tested':False}));raise SystemExit(0 if r['passed'] else 1)
