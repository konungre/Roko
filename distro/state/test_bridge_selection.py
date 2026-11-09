import json,os,subprocess,sys,unittest
from pathlib import Path
class BridgeSelectionTests(unittest.TestCase):
 def run_bridge(self,mode):
  integration=Path(__file__).resolve().parents[2]/'omega-baseline/integration'
  env={**os.environ,'PYTHONPATH':str(integration),'PYTHONDONTWRITEBYTECODE':'1'}
  env.pop('ROKO_PACKAGE_PLANNER',None)
  if mode is not None:env['ROKO_PACKAGE_PLANNER']=mode
  code="import package_bridge as b,json,sys; r=json.loads(b.plan_single('hello','/nix/store/'+'0'*32+'-fixture',json.dumps({'packages':{},'revision':'fixture','source':'test'})));print(json.dumps({'report':r,'mode':b.PLANNER_MODE,'legacy_imported':'omega_pm.core' in sys.modules}))"
  return subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=10)
 def test_default_preserves_legacy_and_opt_in_is_explicit(self):
  default=self.run_bridge(None);new=self.run_bridge('successor-v2')
  self.assertEqual(default.returncode,0);self.assertEqual(new.returncode,0)
  old,fresh=map(lambda r:json.loads(r.stdout),(default,new))
  self.assertEqual(old['mode'],'legacy');self.assertTrue(old['legacy_imported'])
  self.assertFalse(fresh['legacy_imported']);self.assertEqual(fresh['report']['schema'],2)
  self.assertEqual(old['report']['plan'],fresh['report']['plan'])
  self.assertFalse(fresh['report']['authorizes_actions'])
 def test_unknown_mode_fails_closed(self):
  self.assertNotEqual(self.run_bridge('auto').returncode,0)
