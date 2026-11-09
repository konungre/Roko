"""Admission fixtures; never change cgroup limits or allocate guest memory."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from memory_budget import observe,admit
class MemoryBudgetTests(unittest.TestCase):
 def fixture(self,root,limit,current):
  (root/'meminfo').write_text('MemAvailable: 16000000 kB\n');(root/'memory.max').write_text(limit);(root/'memory.current').write_text(current)
  return observe(root/'meminfo',root)
 def test_cgroup_overrides_large_host_free(self):
  with tempfile.TemporaryDirectory() as name:
   row=self.fixture(Path(name),str(16*1024**3),str(16*1024**3-256*1024**2))
   self.assertEqual(row['observed_headroom_bytes'],256*1024**2)
   with self.assertRaises(ValueError):admit(512,observation=row)
 def test_unlimited_cgroup_and_finite_reserve(self):
  with tempfile.TemporaryDirectory() as name:
   row=self.fixture(Path(name),'max','100');self.assertTrue(admit(512,observation=row)['admitted'])
 def test_current_over_limit_and_invalid_configuration_rejected(self):
  with tempfile.TemporaryDirectory() as name:
   row=self.fixture(Path(name),'100','200');self.assertEqual(row['observed_headroom_bytes'],0)
   with self.assertRaises(ValueError):admit(512,observation=row)
  with self.assertRaises(ValueError):admit(512,reserve_mib=0,observation={'observed_headroom_bytes':10**20})
if __name__=='__main__':unittest.main()
