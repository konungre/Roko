"""Cached proof staleness fixtures; no native or runtime readiness proof."""
import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from verify_cached_startup import verify,COSMIC,NETWORK
class CachedStartupTests(unittest.TestCase):
 def setUp(self):
  self.repository=Path(__file__).resolve().parents[2];self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);target=self.root/'distro/nix';target.mkdir(parents=True)
  for name in COSMIC|NETWORK|{'nixpkgs-candidate.json'}:shutil.copy2(self.repository/'distro/nix'/name,target/name)
  evidence=self.repository/'distro/integration/evidence';self.cosmic=json.loads((evidence/'cosmic-ordering-001/result.json').read_text());self.network=json.loads((evidence/'session-network-modes-001/result.json').read_text())
 def test_match_still_never_grants_runtime_readiness(self):
  result=verify(self.root,self.cosmic,self.network);self.assertTrue(result['cached_fragment_source_hashes_match'])
  for key in ('native_evidence_authenticated','commands_replayed','full_nixos_evaluated','runtime_dependencies_verified','image_ready','execution_authorized'):self.assertIs(result[key],False)
 def test_source_drift_and_pin_drift_rejected(self):
  (self.root/'distro/nix/cosmic-session-ordering.nix').write_text('changed source')
  with self.assertRaisesRegex(ValueError,'source changed'):verify(self.root,self.cosmic,self.network)
 def test_semantic_receipt_tamper_and_unexpected_paths_rejected(self):
  cosmic=copy.deepcopy(self.cosmic);cosmic['source_hashes']['../../unrelated']=cosmic['source_hashes'].pop('cosmic_session_report.py')
  with self.assertRaises(ValueError):verify(self.root,cosmic,self.network)
  network=copy.deepcopy(self.network);next(r for r in network['cases'] if r['case']=='managed')['evaluation']['services']['avahi']['enable']=False
  with self.assertRaises(ValueError):verify(self.root,self.cosmic,network)
  cosmic=copy.deepcopy(self.cosmic);cosmic['session_fragment']['requires']=['network-online.target']
  with self.assertRaises(ValueError):verify(self.root,cosmic,self.network)
  network=copy.deepcopy(self.network);network['nixpkgs_pin']['revision']='changed'
  with self.assertRaises(ValueError):verify(self.root,self.cosmic,network)
if __name__=='__main__':unittest.main()
