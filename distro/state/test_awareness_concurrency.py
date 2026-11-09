import sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'omega-baseline/adapters'))
from package_awareness_v2 import SnapshotAwareness
from package_awareness_store_v2 import AwarenessStore
class Runtime:
 def __init__(self):self.atoms=[]
 def parse_all(self,s):return s.splitlines()
 def space(self):return self
 def add_atom(self,a):self.atoms.append(a)
class Backend:
 identity='read-only-concurrency-fixture'
 def observe(self):return SimpleNamespace(packages={},revision='new')
class AwarenessConcurrencyTests(unittest.TestCase):
 def test_late_observation_cannot_replace_newer_refresh(self):
  entered=threading.Event();release=threading.Event();errors=[]
  class Blocking(Backend):
   def observe(self):
    if threading.current_thread().name=='slow-fixture':
     entered.set()
     if not release.wait(3):raise RuntimeError('fixture timeout')
     return SimpleNamespace(packages={'old':'/nix/store/'+'0'*32+'-fixture'},revision='old')
    return super().observe()
  a=SnapshotAwareness(Blocking(),Runtime)
  def slow():
   try:a.refresh()
   except Exception as e:errors.append(str(e))
  thread=threading.Thread(target=slow,name='slow-fixture');thread.start()
  try:self.assertTrue(entered.wait(3));new=a.refresh()
  finally:release.set();thread.join(3)
  self.assertFalse(thread.is_alive());self.assertEqual(errors,['superseded refresh']);self.assertIs(a.current,new);self.assertEqual(new.snapshot.packages,{})
 def test_cooperative_publishers_require_explicit_restore_after_stale_cas(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'checkpoint';sa=AwarenessStore(root);sb=AwarenessStore(root)
   try:
    a=SnapshotAwareness(Backend(),Runtime,sa);b=SnapshotAwareness(Backend(),Runtime,sb);old=a.refresh()
    with self.assertRaises(ValueError):b.refresh()
    self.assertIsNone(b.current);restored=b.restore();self.assertEqual(restored.origin,'restored-historical-checkpoint');self.assertNotEqual(old.token[0],restored.token[0])
    fresh=b.refresh();self.assertEqual(fresh.token[-1],2)
    with self.assertRaises(ValueError):a.refresh()
    self.assertIs(a.current,old)
   finally:sa.close();sb.close()
 def test_corrupt_restore_preserves_current_and_does_not_auto_repair(self):
  with tempfile.TemporaryDirectory() as d:
   s=AwarenessStore(Path(d)/'checkpoint')
   try:
    a=SnapshotAwareness(Backend(),Runtime,s);old=a.refresh();s.db.execute('UPDATE observations SET version=version+1')
    with self.assertRaises(ValueError):a.restore()
    self.assertIs(a.current,old)
    with self.assertRaises(ValueError):a.refresh()
   finally:s.close()
