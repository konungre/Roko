"""Compare read-only fixture awareness contracts; NOT native Hyperon evidence."""
import argparse,json,os,subprocess,sys
from pathlib import Path
WORKER=r'''
import json,sys
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
if sys.argv[3]=='legacy':
 from omega_pm.metta import OmegaAwareness as Awareness
else:
 from package_awareness_v2 import SnapshotAwareness as Awareness
class Runtime:
 def __init__(self):self.atoms=[];self.queries=[]
 def parse_all(self,source):return [line for line in source.splitlines() if line and not line.startswith(';')]
 def space(self):return self
 def add_atom(self,atom):self.atoms.append(atom)
class Backend:
 identity='read-only-fixture'
 def __init__(self):self.packages={'hello':'/nix/store/'+'0'*32+'-fixture'};self.revision='1';self.calls=0
 def observe(self):self.calls+=1;return SimpleNamespace(packages=dict(self.packages),revision=self.revision)
b=Backend();a=Awareness(b,Runtime);old=a.refresh();b.packages={};b.revision='2';new=a.refresh()
assert old.runtime is not new.runtime and any(x.startswith('(installed ') for x in old.runtime.atoms) and not any(x.startswith('(installed ') for x in new.runtime.atoms)
saved=a.current
def broken():raise RuntimeError('fixture failure')
a.runtime_factory=broken
try:a.refresh()
except Exception:failed=True
else:failed=False
assert failed and a.current is saved
b.revision='\") !(exec "not-run")\n';a.runtime_factory=Runtime;escaped=a.refresh()
assert len(escaped.runtime.atoms)==2 and escaped.runtime.atoms[-1]=='(state-revision '+json.dumps(b.revision)+')'
print(json.dumps({'initial_atoms':old.runtime.atoms,'removed_atoms':new.runtime.atoms,'escaped_atoms':escaped.runtime.atoms,'backend':new.backend,'revision':new.snapshot.revision,'failed_refresh_preserved':failed and saved is new,'query_calls':new.runtime.queries,'backend_observations':b.calls,'legacy_imported':'omega_pm.core' in sys.modules}))
'''
def qualify(repository,output):
 root=Path(repository).resolve();output=Path(output).resolve();output.mkdir(mode=0o700);rows=[]
 for mode in ('legacy','successor-v2'):
  r=subprocess.run([sys.executable,'-B','-c',WORKER,str(root/'omega-baseline/adapters'),str(root/'omega-baseline/components/omega-pm'),mode],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=10)
  (output/(mode+'.stdout')).write_text(r.stdout);(output/(mode+'.stderr')).write_text(r.stderr)
  if r.returncode:raise RuntimeError(r.stderr)
  rows.append(json.loads(r.stdout))
 fields=('initial_atoms','removed_atoms','escaped_atoms','backend','revision','failed_refresh_preserved','query_calls','backend_observations')
 passed=all(rows[0][k]==rows[1][k] for k in fields) and not rows[1]['legacy_imported'] and not rows[1]['query_calls']
 report={'passed':passed,'fixture_parity_fields':list(fields),'results':rows,'native_hyperon_tested':False,'package_mutations':0,'legacy_binding_changed':False,'license_clearance':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.output);print(json.dumps({'passed':r['passed'],'native_hyperon_tested':False}));raise SystemExit(0 if r['passed'] else 1)
