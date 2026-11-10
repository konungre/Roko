import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'omega-baseline/adapters'))
from package_awareness_v2 import SnapshotAwareness
class Runtime:
 def __init__(self):self.atoms=[]
 def parse_all(self,source):return source.splitlines()
 def space(self):return self
 def add_atom(self,atom):self.atoms.append(atom)
class Backend:
 identity='read-only-fixture'
 def observe(self):return SimpleNamespace(packages={'hello':'/nix/store/'+'0'*32+'-fixture'},revision='1')
 def install(self,*args):raise AssertionError('mutation forbidden')
 def remove(self,*args):raise AssertionError('mutation forbidden')
class AwarenessSuccessorTests(unittest.TestCase):
 def test_current_runtime_reuse_rejected_before_append(self):
  a=SnapshotAwareness(Backend(),Runtime);old=a.refresh();atoms=list(old.runtime.atoms);a.runtime_factory=lambda:old.runtime
  with self.assertRaises(ValueError):a.refresh()
  self.assertIs(a.current,old);self.assertEqual(old.runtime.atoms,atoms);self.assertFalse(old.authorizes_actions);self.assertFalse(old.live_hyperon_verified)
 def test_partial_fresh_publish_failure_preserves_current(self):
  class Broken(Runtime):
   def add_atom(self,atom):
    if self.atoms:raise RuntimeError('fixture sink failure')
    super().add_atom(atom)
  a=SnapshotAwareness(Backend(),Runtime);old=a.refresh();atoms=list(old.runtime.atoms);a.runtime_factory=Broken
  with self.assertRaises(RuntimeError):a.refresh()
  self.assertIs(a.current,old);self.assertEqual(old.runtime.atoms,atoms)
