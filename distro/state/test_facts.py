import unittest
from facts import *
class FactsTests(unittest.TestCase):
 def test_no_inferred_running(self):
  f=Fact('machine','nix',1,Stage.BUILT,'generation','a'*64,'0'*64)
  self.assertIn(' built ',f.atom());self.assertNotIn('running',f.atom())
 def test_injection_rejected(self):
  with self.assertRaises(ValueError):Fact('machine) (activate','nix',1,Stage.BUILT,'g','a'*64,'0'*64)
 def test_review_and_revision(self):
  calls=[];p=Proposal('activate',2,'g','a'*64)
  e=Executor(lambda p:False,{'activate':lambda p:calls.append(p)})
  with self.assertRaises(PermissionError):e.execute(p,2)
  with self.assertRaises(ValueError):e.execute(p,3)
  self.assertEqual(calls,[])
  Executor(lambda p:True,{'activate':lambda p:calls.append(p)}).execute(p,2)
  self.assertEqual(calls,[p])
if __name__=='__main__':unittest.main()
