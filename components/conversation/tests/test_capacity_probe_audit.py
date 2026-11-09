"""Tamper checks use captured real endpoint evidence, never run a model."""
import json,os,pathlib,shutil,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from probe_eight_turn_capacity import audit
FIXTURE=os.environ.get('ROKO_CAPACITY_AUDIT_FIXTURE')
@unittest.skipUnless(FIXTURE,'Set ROKO_CAPACITY_AUDIT_FIXTURE to captured capacity evidence')
class CapacityAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
        for p in pathlib.Path(FIXTURE).iterdir():
            if p.suffix in ('.json','.jsonl','.txt'):shutil.copy2(p,self.root/p.name)
    def test_captured_evidence_passes(self):self.assertTrue(audit(self.root)['passed'])
    def test_restart_request_tamper_is_rejected(self):
        p=self.root/'restart-requests.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
        rows[1]['expected_revision']+=1;p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
        result=audit(self.root);self.assertFalse(result['passed']);self.assertFalse(result['checks']['restart_request_contract'])
    def test_extra_failed_native_attempt_is_rejected(self):
        p=self.root/'stderr.txt';rows=p.read_text().splitlines()
        for i,line in enumerate(rows):
            if line.startswith('ROKO_FRESH_CONVERSATION '):
                receipt=json.loads(line.split(' ',1)[1]);receipt['native_calls'].append(dict(receipt['native_calls'][0]));rows[i]='ROKO_FRESH_CONVERSATION '+json.dumps(receipt);break
        else:self.fail('Missing native receipt')
        p.write_text('\n'.join(rows)+'\n');result=audit(self.root)
        self.assertFalse(result['passed']);self.assertFalse(result['checks']['native_attempt_contract'])
if __name__=='__main__':unittest.main()
