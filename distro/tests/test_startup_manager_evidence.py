"""Serial parser and host-refusal tests; fixtures are not native boot proof."""
import json,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from startup_manager_evidence import parse,parse_model_delay
class ManagerEvidenceTests(unittest.TestCase):
 def data(self):
  report={'status':'unqualified','system_ready':False,'execution_authorized':False,'boot_id':'fixture','issues':['model-not-qualified']}
  rows=[{'phase':'missing-model-network-unavailable','network_unavailable':True,'report':report},{'phase':'invalid-policy','report':{**report,'status':'failed'}},{'phase':'recovery','report':dict(report)}]
  return ('ROKO_MANAGER_FIXTURE_BEGIN\nroko-startup-report.service: User lookup succeeded: uid=62000 gid=62000\n'+'\n'.join('ROKO_MANAGER_PHASE '+json.dumps(row) for row in rows)+'\nROKO_MANAGER_FIXTURE_PASS\n').encode()
 def test_complete_contract_is_only_serial_consistency(self):self.assertTrue(parse(self.data())['serial_contract_passed'])
 def test_failure_missing_identity_and_false_readiness_rejected(self):
  for old,new in [(b'FIXTURE_PASS',b'FIXTURE_FAIL'),(b'uid=62000',b'uid=0'),(b'"system_ready": false',b'"system_ready": true'),(b'"network_unavailable": true',b'"network_unavailable": false'),(b'"status": "failed"',b'"status": "unqualified"')]:
   with self.subTest(old=old),self.assertRaises(ValueError):parse(self.data().replace(old,new))
 def model_delay(self):
  asset={'status':'asset-observed-not-inference-qualified','bytes':4096,'writer_uid':62000,'inference_qualified':False,'system_ready':False,'execution_authorized':False,'model_sha256_verified_in_guest':False}
  rows=[{'phase':'absent-after-startup','system_ready':False},{'phase':'available-after-startup','asset':asset,'read_only_mount':True,'asset_started_usec':2,'startup_exit_usec':1},{'phase':'removed-again','system_ready':False},{'phase':'asset-recovery','asset':asset,'read_only_mount':True,'asset_started_usec':3,'startup_exit_usec':1}]
  return ('\n'.join('ROKO_MODEL_DELAY_PHASE '+json.dumps(row) for row in rows)+'\nROKO_MODEL_DELAY_FIXTURE_PASS\n').encode()
 def test_asset_availability_never_attests_inference(self):
  result=parse_model_delay(self.model_delay(),4096);self.assertTrue(result['serial_contract_passed']);self.assertFalse(result['inference_qualified'])
 def test_model_order_false_readiness_and_wrong_identity_rejected(self):
  for old,new in [(b'"inference_qualified": false',b'"inference_qualified": true'),(b'"writer_uid": 62000',b'"writer_uid": 0'),(b'"asset_started_usec": 2',b'"asset_started_usec": 1'),(b'"read_only_mount": true',b'"read_only_mount": false')]:
   with self.subTest(old=old),self.assertRaises(ValueError):parse_model_delay(self.model_delay().replace(old,new),4096)
  with self.assertRaises(ValueError):parse_model_delay(self.model_delay(),4097)
 def test_host_controller_refuses_before_side_effects(self):
  controller=Path(__file__).resolve().parents[1]/'integration/startup_manager_controller.py'
  result=subprocess.run([sys.executable,str(controller)],capture_output=True,text=True,timeout=5)
  self.assertEqual(result.returncode,77);self.assertEqual(result.stdout,'');self.assertEqual(result.stderr,'')
if __name__=='__main__':unittest.main()
