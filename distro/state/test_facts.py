import unittest
from facts import *
class FactsTests(unittest.TestCase):
 def test_no_inferred_running(self):
  f=Fact('machine','nix',1,Stage.BUILT,'generation','a'*64,'0'*64)
  self.assertIn(' built ',f.atom());self.assertNotIn('running',f.atom())
 def test_injection_rejected(self):
  with self.assertRaises(ValueError):Fact('machine) (activate','nix',1,Stage.BUILT,'g','a'*64,'0'*64)
 def test_review_time_change_and_replay(self):
  import tempfile
  from pathlib import Path
  from revisions import RevisionGate
  with tempfile.TemporaryDirectory() as d:
   gate=RevisionGate(Path(d)/'gate');calls=[];p=Proposal('activate',0,'g','a'*64)
   def review(proposal):
    with gate.reserve(0):pass
    return True
   e=Executor(review,{'activate':lambda p:calls.append(p)},gate)
   with self.assertRaises(ValueError):e.execute(p)
   self.assertEqual(calls,[])
   approved=Executor(lambda p:True,{'activate':lambda p:calls.append(p)},gate)
   q=Proposal('activate',1,'g','a'*64);approved.execute(q)
   with self.assertRaises(ValueError):approved.execute(q)
   self.assertEqual(calls,[q])
 def test_unreviewed_does_not_reserve(self):
  import tempfile
  from pathlib import Path
  from revisions import RevisionGate
  with tempfile.TemporaryDirectory() as d:
   gate=RevisionGate(Path(d)/'gate')
   with self.assertRaises(PermissionError):Executor(lambda p:False,{},gate).execute(Proposal('activate',0,'g','a'*64))
   with gate.reserve(0):pass
