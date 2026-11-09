import tempfile,unittest
from pathlib import Path
from facts import Fact,Stage
from ledger import Ledger
class LedgerTests(unittest.TestCase):
 def test_restart_stale_and_simulation(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'state.db';l=Ledger(path)
   f=Fact('test','nix',1,Stage.OBSERVED,'generation','a'*64,'0'*64)
   h=l.append(f,0);l.close();l=Ledger(path)
   self.assertEqual(l.latest('test','nix')[1],h)
   with self.assertRaises(ValueError):l.append(f,0)
   g=Fact('test','nix',2,Stage.ACTIVATED,'generation','b'*64,h)
   l.append(g,1,'simulation');self.assertEqual(l.latest('test','nix')[0]['mode'],'simulation');l.close()
