import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from audit_derivation_graph import audit
class DerivationGraphTests(unittest.TestCase):
 def fixture(self,directory):
  root=Path(directory);graph={'image.drv':{'inputDrvs':{'tool.drv':{'outputs':['out'],'dynamicOutputs':{}}},'outputs':{'out':{'path':str(root/'missing-image')}},'env':{'name':'image'}},'tool.drv':{'inputDrvs':{},'outputs':{'out':{'path':str(root/'tool')},'debug':{'path':str(root/'unused-debug')}},'env':{'name':'tool'}}}
  (root/'tool').write_text('present');(root/'graph.json').write_text(json.dumps(graph));(root/'identities.json').write_text(json.dumps({'evaluations':[{'mode':'headless','identities':{'imageDerivation':'image.drv'}}]}));return root,graph
 def test_only_requested_outputs_count(self):
  with tempfile.TemporaryDirectory() as d:
   root,_=self.fixture(d);r=audit(root/'graph.json',root/'identities.json',root/'report.json')['roots'][0]
   self.assertEqual(r['required_output_pairs'],2);self.assertEqual(r['required_outputs_present'],1);self.assertEqual(r['required_outputs_missing'],1)
 def test_missing_graph_metadata_is_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   root,g=self.fixture(d);del g['tool.drv'];(root/'graph.json').write_text(json.dumps(g));r=audit(root/'graph.json',root/'identities.json',root/'report.json')['roots'][0]
   self.assertEqual(r['incomplete_metadata'],['tool.drv']);self.assertEqual(r['unknown_outputs'],[['tool.drv','out']])
 def test_existing_checkpoint_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   root,_=self.fixture(d);report=root/'report.json';report.write_text('checkpoint')
   with self.assertRaises(FileExistsError):audit(root/'graph.json',root/'identities.json',report)
   self.assertEqual(report.read_text(),'checkpoint')
