import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from qualify_offline_closure import qualify
class OfflineClosureTests(unittest.TestCase):
 def test_remote_or_flag_root_rejected_before_nix(self):
  for value in ('github:NixOS/nixpkgs#hello','--repair','/tmp/not-store.drv'):
   with self.subTest(root=value),tempfile.TemporaryDirectory() as d:
    p=Path(d);request=p/'roots.json';request.write_text(json.dumps({'scope':'image','roots':[{'label':'bad','derivation':value}]}))
    with patch('qualify_offline_closure.subprocess.run') as runner:
     with self.assertRaises(ValueError):qualify(p/'base',request,p/'report')
     runner.assert_not_called()
 def test_scope_must_be_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);request=p/'roots.json';request.write_text(json.dumps({'roots':[]}))
   with self.assertRaises(ValueError):qualify(p/'base',request,p/'report')
