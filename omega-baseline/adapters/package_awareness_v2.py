"""Opt-in read-only snapshot awareness using a caller-owned fresh runtime factory.

No Hyperon import, runtime download, desired-rule evaluation or package executor.
Native Hyperon compatibility and long-lived subscription remain unqualified.
"""
from dataclasses import dataclass
import json
from package_planning_v2 import SnapshotOnly
@dataclass(frozen=True)
class Observation:
 backend:str
 snapshot:object
 runtime:object
 authorizes_actions:bool=False
 live_hyperon_verified:bool=False
class SnapshotAwareness:
 def __init__(self,backend,runtime_factory):
  if not callable(runtime_factory):raise ValueError('explicit fresh runtime factory required')
  self.backend=backend;self.runtime_factory=runtime_factory;self.current=None
 def refresh(self):
  observed=self.backend.observe()
  validated=SnapshotOnly(json.dumps({'packages':observed.packages,'revision':observed.revision,'source':self.backend.identity})).observe()
  lines=['(omega-state 1)']
  for name,path in sorted(validated.packages.items()):lines.append('(installed '+name+' '+json.dumps(path)+')')
  lines.append('(state-revision '+json.dumps(validated.revision)+')')
  runtime=self.runtime_factory()
  if self.current is not None and runtime is self.current.runtime:raise ValueError('fresh dedicated runtime required')
  atoms=list(runtime.parse_all('\n'.join(lines)+'\n'));space=runtime.space()
  for atom in atoms:space.add_atom(atom)
  result=Observation(self.backend.identity,validated,runtime)
  self.current=result
  return result
