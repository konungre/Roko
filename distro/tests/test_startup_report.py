"""Local diagnostic program tests; not systemd or guest boot evidence."""
import contextlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nix'))
from startup_report import inspect,run
class StartupReportTests(unittest.TestCase):
 def policy(self):return {'schema':'roko-first-boot-policy-v1','offlineRequested':True,'networkIsolationProven':False,'automaticUpgrade':False,'automaticGenerationDeletion':False,'modelReady':False,'durableHistoryReady':False,'credentialProvisioningRequired':True}
 def test_unqualified_is_not_runtime_failure_or_readiness(self):
  report=inspect(self.policy(),'00000000-0000-0000-0000-000000000001')
  self.assertEqual(report['status'],'unqualified');self.assertIn('model-not-qualified',report['issues']);self.assertIn('credentials-not-provisioned',report['issues']);self.assertFalse(report['system_ready']);self.assertFalse(report['execution_authorized'])
 def test_optimistic_policy_does_not_attest_runtime(self):
  policy=self.policy();policy.update(modelReady=True,durableHistoryReady=True,credentialProvisioningRequired=False,networkIsolationProven=True)
  report=inspect(policy,'00000000-0000-0000-0000-000000000001')
  self.assertEqual(report['issues'],['runtime-health-not-observed']);self.assertFalse(report['system_ready'])
 def test_invalid_policy_replaces_stale_success_with_sanitized_failure(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);policy=root/'policy';output=root/'status';boot=root/'boot'
   boot.write_text('00000000-0000-0000-0000-000000000001\n');policy.write_text(json.dumps(self.policy()))
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(policy,output,boot),0)
   policy.write_text('{"schema":"private-secret-do-not-log","schema":"duplicate"}')
   logs=io.StringIO()
   with contextlib.redirect_stdout(logs):self.assertEqual(run(policy,output,boot),1)
   report=json.loads(output.read_text());self.assertEqual(report['status'],'failed');self.assertFalse(report['system_ready'])
   self.assertNotIn('private-secret',logs.getvalue()+output.read_text());self.assertEqual(output.stat().st_mode&0o777,0o640);self.assertEqual(list(root.glob('.startup-*')),[])
 def test_missing_policy_or_invalid_boot_identity_fails_closed(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);boot=root/'boot';policy=root/'policy';output=root/'status';boot.write_text('invalid')
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(policy,output,boot),1)
   policy.write_text(json.dumps(self.policy()))
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(policy,output,boot),1)
 def test_failed_publication_preserves_complete_prior_report_and_raises(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);policy=root/'policy';output=root/'status';boot=root/'boot'
   boot.write_text('00000000-0000-0000-0000-000000000001');policy.write_text(json.dumps(self.policy()))
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(policy,output,boot),0)
   previous=output.read_bytes();boot.write_text('00000000-0000-0000-0000-000000000002')
   with patch('startup_report.os.replace',side_effect=OSError('fixture publication failure')):
    with self.assertRaises(OSError):run(policy,output,boot)
   self.assertEqual(output.read_bytes(),previous);self.assertEqual(list(root.glob('.startup-*')),[])
 def test_nonboolean_policy_and_unexpected_fields_rejected(self):
  for field,value in [('modelReady',1),('newField',False)]:
   policy=self.policy();policy[field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):inspect(policy,'00000000-0000-0000-0000-000000000001')
if __name__=='__main__':unittest.main()
