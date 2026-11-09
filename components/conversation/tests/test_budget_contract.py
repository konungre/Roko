import pathlib,sys,unittest,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from fresh import budget_contract,generation_metadata,GenerationError
class BudgetContractTests(unittest.TestCase):
 def test_default_stays512(self):self.assertEqual(budget_contract({})['input_tokens'],512)
 def test_explicit768(self):self.assertEqual(budget_contract({'native_budget':dict(kind='roko-native-budget-v1',input_tokens=768,context_tokens=1024,max_output_tokens=128)})['input_tokens'],768)
 def test_bad_contracts(self):
  base=dict(kind='roko-native-budget-v1',input_tokens=768,context_tokens=1024,max_output_tokens=128)
  for value in (None,{},dict(base,input_tokens=True),dict(base,input_tokens=769),dict(base,context_tokens=768),dict(base,max_output_tokens=129),dict(base,extra=True)):
   with self.subTest(value=value),self.assertRaises(ValueError):budget_contract({'native_budget':value})
 def test_receipt_limit_follows_contract(self):
  receipt=lambda n:'ROKO_GENERATION '+json.dumps(dict(input_tokens=n,output_tokens=7,finish_reason='eos'))
  with self.assertRaises(GenerationError):generation_metadata(receipt(677),32)
  self.assertEqual(generation_metadata(receipt(677),32,768)['input_tokens'],677)
  with self.assertRaises(GenerationError):generation_metadata(receipt(769),32,768)

class CapabilityReceiptTests(unittest.TestCase):
 def profile(self,limit=768):return dict(python=sys.executable,infer='/explicit/pinned/infer',native_budget=dict(kind='roko-native-budget-v1',input_tokens=limit,context_tokens=1024,max_output_tokens=128))
 def test_legacy_does_not_require_new_runner_command(self):
  from fresh import verify_budget_capability
  from unittest.mock import patch
  with patch('fresh.subprocess.run') as run:
   verify_budget_capability({});run.assert_not_called()
 def test_exact_capability_receipt(self):
  from fresh import verify_budget_capability
  from unittest.mock import patch
  from types import SimpleNamespace
  p=self.profile();receipt=SimpleNamespace(returncode=0,stdout=json.dumps(p['native_budget']).encode(),stderr=b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1\n')
  with patch('fresh.subprocess.run',return_value=receipt):verify_budget_capability(p)
 def test_changed_capability_or_missing_cleanup_fails(self):
  from fresh import verify_budget_capability
  from unittest.mock import patch
  from types import SimpleNamespace
  p=self.profile()
  for body,stderr in ((dict(p['native_budget'],input_tokens=512),b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1'),(dict(p['native_budget'],input_tokens=True),b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1'),(p['native_budget'],b'')):
   with self.subTest(body=body,stderr=stderr),patch('fresh.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(body).encode(),stderr=stderr)),self.assertRaises(ValueError):verify_budget_capability(p)
 def test_duplicate_capability_fields_fail(self):
  from fresh import verify_budget_capability
  from unittest.mock import patch
  from types import SimpleNamespace
  body=b'{"kind":"roko-native-budget-v1","input_tokens":512,"input_tokens":768,"context_tokens":1024,"max_output_tokens":128}'
  with patch('fresh.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=body,stderr=b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1')),self.assertRaises(ValueError):verify_budget_capability(self.profile())

if __name__=='__main__':unittest.main()
