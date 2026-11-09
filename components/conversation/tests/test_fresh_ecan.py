import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fresh_ecan


class ECANAdmissionTests(unittest.TestCase):
    def test_code_like_identity_rejected_before_native_launch(self):
        with self.assertRaises(ValueError):
            fresh_ecan.rank_candidates([dict(id='x) !(shell evil)',sti=1,lti=1,stimulus=0)],profile={})

    def test_bool_attention_rejected(self):
        with self.assertRaises(ValueError):
            fresh_ecan.rank_candidates([dict(id='ctx_0',sti=True,lti=1,stimulus=0)],profile={})

    def test_modified_lock_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); lock=root/'lock.json'; lock.write_text('{}')
            profile={'ecan':{'source':directory,'lock':str(lock)},'files':{str(lock):'0'*64}}
            with self.assertRaisesRegex(fresh_ecan.NativeECANError,'source lock'):
                fresh_ecan.verify_source(profile)

    def test_modified_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'module.metta';source.write_text('changed')
            lock=root/'lock.json';expected=hashlib.sha256(b'original').hexdigest()
            lock.write_text(json.dumps({'commit':fresh_ecan.COMMIT,'files':{'module.metta':expected}}))
            profile={'ecan':{'source':directory,'lock':str(lock)},'files':{
                str(lock):hashlib.sha256(lock.read_bytes()).hexdigest(),str(source):expected}}
            with self.assertRaisesRegex(fresh_ecan.NativeECANError,'source mismatch'):
                fresh_ecan.verify_source(profile)


@unittest.skipUnless(os.environ.get('ROKO_ECAN_TEST_PROFILE'),'Requires pinned external ECAN/native runtime')
class ECANNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=json.loads(Path(os.environ['ROKO_ECAN_TEST_PROFILE']).read_text())

    def test_actual_focus_and_stimulus_and_conservation(self):
        candidates=[dict(id='ctx_'+str(i),sti=s,lti=10,stimulus=0) for i,s in enumerate([100,80,60,40,39])]
        original=copy.deepcopy(candidates)
        before,receipt=fresh_ecan.rank_candidates(candidates,profile=self.profile)
        self.assertEqual(candidates,original)
        self.assertEqual(before['focus'],['ctx_0','ctx_1','ctx_2','ctx_3'])
        candidates[-1]['stimulus']=10
        after,receipt2=fresh_ecan.rank_candidates(candidates,profile=self.profile)
        self.assertIn('ctx_4',after['focus'])
        self.assertNotIn('ctx_3',after['focus'])
        self.assertGreater(next(x['sti'] for x in after['ranking'] if x['id']=='ctx_4'),39)
        for result,r in [(before,receipt),(after,receipt2)]:
            self.assertEqual(r['returncode'],0)
            self.assertTrue(r['source_prepost_verified'])
            self.assertIn('descendants_cleaned=1',r['stderr'])
            self.assertEqual(result['funds']['sti']+sum(x['sti'] for x in result['ranking']),100000)
            self.assertFalse(result['authorizes_actions'])


if __name__=='__main__':unittest.main()
