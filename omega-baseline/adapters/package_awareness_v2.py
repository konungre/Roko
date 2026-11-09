"""Opt-in read-only awareness; no native Hyperon compatibility claim or executor."""
from dataclasses import dataclass
import json,threading,uuid
from package_planning_v2 import SnapshotOnly
@dataclass(frozen=True)
class Observation:
 backend:str
 snapshot:object
 runtime:object
 origin:str='backend-observation'
 token:tuple=()
 authorizes_actions:bool=False
 live_hyperon_verified:bool=False
class SnapshotAwareness:
 def __init__(self,backend,runtime_factory,store=None):
  if not callable(runtime_factory):raise ValueError('explicit fresh runtime factory required')
  self.backend=backend;self.runtime_factory=runtime_factory;self.current=None;self.store=store
  self._lock=threading.RLock();self._epoch=uuid.uuid4().hex;self._started=0
  self._version=store.load(backend.identity)['version'] if store is not None else 0
 def _ticket(self):
  with self._lock:self._started+=1;return self._started
 def _runtime(self,snapshot):
  lines=['(omega-state 1)']
  for name,path in sorted(snapshot.packages.items()):lines.append('(installed '+name+' '+json.dumps(path)+')')
  lines.append('(state-revision '+json.dumps(snapshot.revision)+')')
  runtime=self.runtime_factory()
  with self._lock:
   if self.current is not None and runtime is self.current.runtime:raise ValueError('fresh dedicated runtime required')
  atoms=list(runtime.parse_all('\n'.join(lines)+'\n'));space=runtime.space()
  for atom in atoms:space.add_atom(atom)
  return runtime
 def refresh(self):
  ticket=self._ticket();observed=self.backend.observe()
  snapshot=SnapshotOnly(json.dumps({'packages':observed.packages,'revision':observed.revision,'source':self.backend.identity})).observe()
  runtime=self._runtime(snapshot)
  with self._lock:
   if ticket!=self._started:raise ValueError('superseded refresh')
   if self.store is not None:self._version=self.store.save(self.backend.identity,snapshot,self._version)
   result=Observation(self.backend.identity,snapshot,runtime,'backend-observation',(self._epoch,ticket,self._version))
   self.current=result;return result
 def restore(self):
  if self.store is None:raise ValueError('explicit checkpoint required')
  ticket=self._ticket();saved=self.store.load(self.backend.identity)
  if saved['snapshot'] is None:raise ValueError('no checkpoint to restore')
  runtime=self._runtime(saved['snapshot'])
  with self._lock:
   if ticket!=self._started or self.store.load(self.backend.identity)['version']!=saved['version']:raise ValueError('superseded checkpoint restore')
   self._version=saved['version']
   result=Observation(self.backend.identity,saved['snapshot'],runtime,'restored-historical-checkpoint',(self._epoch,ticket,self._version))
   self.current=result;return result
