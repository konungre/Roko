"""Failure fixtures for optional native observer; not native execution evidence."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'omega-baseline/adapters'))
from package_profile_observation_v2 import ReadOnlyProfile
class ProfileObservationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.target=self.root/'generation';self.target.mkdir();(self.target/'manifest.json').write_text('{}')
  self.profile=self.root/'profile';self.profile.symlink_to(self.target)
  self.backend=ReadOnlyProfile(['fixture-nix'],self.profile,{})
 def response(self,value):return SimpleNamespace(returncode=0,stdout=json.dumps(value),stderr='')
 def test_missing_is_not_empty(self):
  self.profile.unlink()
  with patch('package_profile_observation_v2.subprocess.run') as run:
   with self.assertRaises(ValueError):self.backend.observe()
   run.assert_not_called()
 def test_malformed_and_unsupported_native_output(self):
  cases=['[]','{"version":3,"version":3,"elements":{}}','{"version":2,"elements":{}}','{"version":3,"elements":{"x":{"storePaths":["a","b"]}}}']
  for source in cases:
   with self.subTest(source=source),patch('package_profile_observation_v2.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=source,stderr='')):
    with self.assertRaises(ValueError):self.backend.observe()
    self.assertIsNone(self.backend.last_receipt)
 def test_observed_drift_preserves_last_receipt(self):
  with patch('package_profile_observation_v2.subprocess.run',return_value=self.response({'version':3,'elements':{}})):self.backend.observe()
  previous=self.backend.last_receipt
  def drift(*args,**kwargs):
   (self.target/'manifest.json').write_text('{"changed":true}')
   return self.response({'version':3,'elements':{}})
  with patch('package_profile_observation_v2.subprocess.run',side_effect=drift):
   with self.assertRaisesRegex(ValueError,'changed during observation'):self.backend.observe()
  self.assertIs(self.backend.last_receipt,previous)
 def test_native_failure_is_not_empty(self):
  with patch('package_profile_observation_v2.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='fixture unavailable')):
   with self.assertRaisesRegex(ValueError,'observation failed'):self.backend.observe()
  self.assertIsNone(self.backend.last_receipt)
if __name__=='__main__':unittest.main()
