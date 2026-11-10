"""Admission fixtures; never change cgroup limits or allocate guest memory."""
import sys,tempfile,unittest,os,subprocess
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
 def test_wrong_units_duplicate_values_and_oversized_counters_rejected(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);self.fixture(root,'max','0')
   for text in ('MemAvailable: 16000000 MB\n','MemAvailable: 1 kB\nMemAvailable: 2 kB\n','MemAvailable: -1 kB\n'):
    (root/'meminfo').write_text(text)
    with self.subTest(text=text),self.assertRaises(ValueError):observe(root/'meminfo',root)
   (root/'meminfo').write_text('MemAvailable: 16000000 kB\n');(root/'memory.current').write_text('1'*65)
   with self.assertRaises(ValueError):observe(root/'meminfo',root)
 def test_fifo_and_symlink_counters_fail_without_blocking(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);self.fixture(root,'max','0');(root/'memory.current').unlink();os.mkfifo(root/'memory.current')
   integration=Path(__file__).resolve().parents[1]/'integration'
   code="import sys;sys.path.insert(0,sys.argv[1]);from memory_budget import observe;from pathlib import Path\ntry:observe(Path(sys.argv[2])/'meminfo',Path(sys.argv[2]))\nexcept (OSError,ValueError):raise SystemExit(42)\nraise SystemExit(1)"
   run=subprocess.run([sys.executable,'-I','-B','-c',code,str(integration),str(root)],capture_output=True,text=True,timeout=2);self.assertEqual(run.returncode,42,run.stderr)
   (root/'memory.current').unlink();(root/'other').write_text('0');(root/'memory.current').symlink_to(root/'other')
   with self.assertRaises(OSError):observe(root/'meminfo',root)
if __name__=='__main__':unittest.main()
