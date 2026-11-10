import hashlib,tempfile,unittest
from pathlib import Path
from declarative import desired,Reconciler
class IntentTests(unittest.TestCase):
 def test_provenance_and_paths(self):
  with tempfile.TemporaryDirectory() as d:
   lock=b'pinned-input';p=str(Path(d)/('a'*32+'-output'));doc={'schema':'roko-private-intent-v1','backend':'nix','source_lock_sha256':hashlib.sha256(lock).hexdigest(),'packages':{'hello':p}}
   self.assertEqual(desired(doc,d,lock),{'hello':p})
   with self.assertRaises(ValueError):desired(doc,d,b'changed')
   doc['packages']['hello']='/bin/sh'
   with self.assertRaises(ValueError):desired(doc,d,lock)
 def test_review_does_not_mutate_frozen_plan(self):
  with tempfile.TemporaryDirectory() as d:
   class Backend:
    root=Path(d)
    def current(self):return {'revision':0,'target':None}
    def run(self,*args):return args[-1]
    def switch(self,packages,expected,review):return packages
   r=Reconciler(Backend(),d);lock=b'pin';path=str(Path(d)/('a'*32+'-output'))
   doc={'schema':'roko-private-intent-v1','backend':'nix','source_lock_sha256':hashlib.sha256(lock).hexdigest(),'packages':{'hello':path}}
   plan=r.prepare(doc,lock)
   def review(copy):copy['desired'].clear();plan['desired'].clear();return True
   self.assertEqual(r.apply(plan,lock,review),{'hello':path})
 def test_unknown_authority_field_rejected(self):
  with self.assertRaises(ValueError):desired({'authorized':True},'/nix/store',b'')
