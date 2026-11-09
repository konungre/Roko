import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"session"))
from session_evidence import validate

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(version=1,ok=1,processes=[[pid,1]+[0]*14+[[],0] for pid in (1,2)],
            roles=[[i,pid] for i,pid in enumerate((3,4,5,6,7,2))],
            mounts=[[i,0,0,0,0,0] for i in range(18)],
            metadata=[[i,1000,1000,0o700] for i in range(3)]+[[3,1000,1000,0o770],[4,0,1000,0o660]],
            devices=[],fds=[],peer=[1,0,0],server_peer=[8,1000,1000],usability=0,udev=0)
        self.row['processes'] += [[pid,1]+[1000]*8+[0]*5+[1,[],1] for pid in range(3,9)]
        for i in (0,8):self.row['mounts'][i]=[i,1,1,1,0,0]
        for i in (16,17):self.row['mounts'][i]=[i,0,1,1,1,0]

    def log(self):
        return '\n'.join(['ROKO_FOUNDATION_STATE_MOUNTED read','ROKO_EVIDENCE_V1 '+json.dumps(self.row),
            'ROKO_FOUNDATION_STATE_VERIFIED read uid=1000 revision=1',
            'ROKO_DESKTOP_READY uid=1000 inference=not-started'])

    def test_synthetic_contract_only(self):
        result=validate(self.log(),'read')
        self.assertTrue(result['persistent_checkpoint_passed'])
        self.assertFalse(result['visible_desktop_verified'])
        self.assertFalse(result['model_inference_tested'])

    def test_root_or_capable_user_rejected(self):
        baseline=copy.deepcopy(self.row)
        for index,value in ((2,0),(10,1),(13,1),(15,0),(16,[1000]),(17,0)):
            self.row=copy.deepcopy(baseline);self.row['processes'][2][index]=value
            with self.assertRaises(ValueError):validate(self.log(),'read')

    def test_missing_duplicate_role_and_process(self):
        for field in ('processes','roles'):
            baseline=copy.deepcopy(self.row)
            self.row[field].append(self.row[field][0])
            with self.assertRaises(ValueError):validate(self.log(),'read')
            self.row=baseline
        self.row['processes'].pop()
        with self.assertRaises(ValueError):validate(self.log(),'read')

    def test_unsafe_mount_or_private_metadata(self):
        baseline=copy.deepcopy(self.row)
        for index in (0,8,16,17):
            self.row=copy.deepcopy(baseline);self.row['mounts'][index][2]=0
            with self.assertRaises(ValueError):validate(self.log(),'read')
        self.row=baseline;self.row['metadata'][0][-1]=0o777
        with self.assertRaises(ValueError):validate(self.log(),'read')

    def test_marker_and_failure_rejection(self):
        for text in (self.log().replace('VERIFIED read','VERIFIED write'), self.log()+'\nROKO_START_FAILED ValueError', self.log()+'\nROKO_FOUNDATION_STATE_MOUNTED read'):
            with self.assertRaises(ValueError):validate(text,'read')

    def test_boolean_and_extra_schema_rejection(self):
        self.row['ok']=True
        with self.assertRaises(ValueError):validate(self.log(),'read')
        self.row['ok']=1;self.row['executed_actions']=1
        with self.assertRaises(ValueError):validate(self.log(),'read')

if __name__=='__main__':unittest.main()
