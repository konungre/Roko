import importlib.util,json,sys,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('package_planning_v2',Path(__file__).resolve().parents[2]/'omega-baseline/adapters/package_planning_v2.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SuccessorTests(unittest.TestCase):
 def test_snapshot_semantics_and_no_authority(self):
  path='/nix/store/'+'0'*32+'-fixture'
  raw=module.plan_single('hello',path,json.dumps({'packages':{},'source':'fixture','revision':'1'}))
  self.assertEqual(module.operation_count(raw),1);self.assertTrue(module.has_planned_package(raw,'hello',path));self.assertFalse(module.authorizes_actions(raw));self.assertNotIn('omega_pm',sys.modules)
 def test_duplicate_and_executable_rejected(self):
  with self.assertRaises(ValueError):module.plan_single('hello','/bin/sh','{}')
  with self.assertRaises(ValueError):module.plan_single('hello','/nix/store/'+'0'*32+'-fixture','{"packages":{},"packages":{},"revision":"1","source":"f"}')
