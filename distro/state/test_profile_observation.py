"""Failure fixtures for optional native observer; not native execution evidence."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'omega-baseline/adapters'))
from package_profile_observation_v2 import ReadOnlyProfile
from package_awareness_v2 import SnapshotAwareness
from package_awareness_store_v2 import AwarenessStore
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
 def test_populated_canonical_fixture_checkpoint_restart_and_removal(self):
  # Nix output and space are fixtures; no /nix/store output is claimed to exist.
  class Runtime:
   def __init__(self):self.atoms=[]
   def parse_all(self,text):return text.splitlines()
   def space(self):return self
   def add_atom(self,atom):self.atoms.append(atom)
  canonical='/nix/store/'+'0'*32+'-explicit-fixture'
  populated={'version':3,'elements':{'hello':{'active':True,'storePaths':[canonical]},'ignored':{'active':False,'storePaths':['not-an-installed-path']}}}
  store=AwarenessStore(self.root/'checkpoint');awareness=SnapshotAwareness(self.backend,Runtime,store)
  with patch('package_profile_observation_v2.subprocess.run',return_value=self.response(populated)):
   first=awareness.refresh()
  self.assertEqual(first.snapshot.packages,{'hello':canonical});self.assertEqual(first.token[2],1)
  self.assertIn('(installed hello '+json.dumps(canonical)+')',first.runtime.atoms)
  self.assertEqual(self.backend.last_receipt['native'],populated)
  self.assertFalse(first.authorizes_actions)
  old_revision=first.snapshot.revision;store.close()
  restarted_backend=ReadOnlyProfile(['fixture-nix'],self.profile,{})
  reopened=AwarenessStore(self.root/'checkpoint');self.addCleanup(reopened.close)
  restarted=SnapshotAwareness(restarted_backend,Runtime,reopened)
  with patch('package_profile_observation_v2.subprocess.run') as run:
   historical=restarted.restore();run.assert_not_called()
  self.assertEqual(historical.origin,'restored-historical-checkpoint')
  self.assertEqual(historical.snapshot.document(),first.snapshot.document());self.assertEqual(restarted_backend.calls,0)
  self.assertNotEqual(historical.token[0],first.token[0])
  with patch('package_profile_observation_v2.subprocess.run',return_value=self.response({'version':3,'elements':{}})):
   removed=restarted.refresh()
  self.assertEqual(removed.snapshot.packages,{});self.assertNotEqual(removed.snapshot.revision,old_revision)
  self.assertEqual(removed.token[2],2);self.assertEqual(len(removed.runtime.atoms),2)
  self.assertEqual(first.snapshot.packages,{'hello':canonical});self.assertEqual(len(first.runtime.atoms),3)
  invalid={'version':3,'elements':{'hello':{'active':True,'storePaths':[canonical,canonical+'-extra']}}}
  with patch('package_profile_observation_v2.subprocess.run',return_value=self.response(invalid)):
   with self.assertRaisesRegex(ValueError,'single output'):restarted.refresh()
  self.assertIs(restarted.current,removed);self.assertEqual(reopened.load(restarted_backend.identity)['version'],2)
if __name__=='__main__':unittest.main()
