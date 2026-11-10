import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from verify_builder_packet import verify,REQUIRED
class BuilderPacketTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d);pin={'revision':'fixture-only-not-upstream'};files={}
  for name in REQUIRED:
   raw=json.dumps(pin if name=='source-pin.json' else {'fixture':True}).encode();(root/name).write_bytes(raw);files[name]=hashlib.sha256(raw).hexdigest()
  return root,pin,{'schema':'roko-builder-packet-v1','status':'unqualified','files':files}
 def test_matches_never_grants_readiness(self):
  with tempfile.TemporaryDirectory() as d:
   root,pin,m=self.fixture(d);r=verify(root,m,pin)
   self.assertTrue(r['artifact_hashes_match']);self.assertFalse(r['image_ready']);self.assertFalse(r['execution_authorized']);self.assertFalse(r['builder_signature_verified'])
 def test_tamper_and_pin_substitution(self):
  with tempfile.TemporaryDirectory() as d:
   root,pin,m=self.fixture(d)
   with self.assertRaises(ValueError):verify(root,m,{'revision':'different'})
   (root/'roots.json').write_text('{}')
   with self.assertRaises(ValueError):verify(root,m,pin)
 def test_missing_linked_and_qualified_inputs_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root,pin,m=self.fixture(d);m['status']='qualified'
   with self.assertRaises(ValueError):verify(root,m,pin)
   m['status']='unqualified';(root/'roots.json').unlink()
   with self.assertRaises(FileNotFoundError):verify(root,m,pin)
   (root/'roots.json').symlink_to(root/'image-hashes.json')
   with self.assertRaises(OSError):verify(root,m,pin)
