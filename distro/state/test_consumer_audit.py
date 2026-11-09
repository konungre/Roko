import hashlib,subprocess,tempfile,unittest
from pathlib import Path
from audit_planner_consumers import audit
class ConsumerAuditTests(unittest.TestCase):
 def repo(self,root):
  subprocess.run(['git','init','-q',str(root)],check=True)
  (root/'direct.py').write_text('if False:\n from omega_pm.core import Snapshot\n')
  (root/'dynamic.py').write_text("import importlib\nx=importlib.import_module('omega_pm.core')\n")
  subprocess.run(['git','add','.'],cwd=root,check=True)
  subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-c','core.hooksPath=/dev/null','commit','-qm','fixture'],cwd=root,check=True)
 def test_inventory_is_read_only_and_does_not_claim_dynamic_completeness(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.repo(root);before={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('direct.py','dynamic.py')};r=audit(root)
   self.assertEqual(len(r['imports']),1);self.assertEqual(len(r['text_references']),2);self.assertFalse(r['deletion_authorized']);self.assertFalse(r['dynamic_imports_known_complete']);self.assertEqual(before,{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in before})
 def test_bad_syntax_is_not_silently_complete(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.repo(root);(root/'bad.py').write_text('from omega_pm.core import (\n');subprocess.run(['git','add','bad.py'],cwd=root,check=True)
   r=audit(root);self.assertEqual(r['parse_errors'],[{'file':'bad.py','line':1}]);self.assertFalse(r['external_callers_known_complete'])
