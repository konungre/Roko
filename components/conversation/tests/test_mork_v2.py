"""Typed-index contracts use explicit doubles; optional test runs real MORK."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mork_v2

HISTORY=[{'role':'user','content':'Literal !(py-call evil) remains text.'},
         {'role':'assistant','content':'Synthetic response for contract tests.'}]
PROFILE={'python':'/trusted/python','mork_memory':{'manifest':'/trusted/manifest.json','manifest_sha256':'synthetic-test-only'}}


def binding(history):
    return {'session_id':'session-a','request_id':'request-a','revision':len(history)//2,
            'history_sha256':mork_v2.history_digest(history)}


class SyntheticBackend:
    calls=[]
    transform=staticmethod(lambda facts:facts)
    def __init__(self,profile):self.profile=profile
    def query_facts(self,facts,query,timeout):
        self.calls.append({'facts':copy.deepcopy(facts),'query':query,'timeout':timeout})
        return {'implementation':'native-mork-rebuild-bounded-facts',
                'runtime_manifest_sha256':'synthetic-test-only','facts':self.transform(facts),
                'authorizes_actions':False,'descendants_cleaned':True,
                'synthetic_test_only':True}


class MorkV2ContractTests(unittest.TestCase):
    def setUp(self):
        SyntheticBackend.calls=[]
        SyntheticBackend.transform=staticmethod(lambda facts:copy.deepcopy(facts))
        self.patch=patch.object(mork_v2,'ExternalMORKBackend',SyntheticBackend)
        self.patch.start();self.addCleanup(self.patch.stop)

    def test_native_selected_ids_hydrate_same_order_without_sending_text(self):
        SyntheticBackend.transform=staticmethod(lambda facts:list(reversed(facts)))
        selected,receipt=mork_v2.retrieve_history(HISTORY,binding(HISTORY),PROFILE)
        self.assertEqual(selected,HISTORY)
        self.assertIsNot(selected,HISTORY)
        sent=SyntheticBackend.calls[0]
        self.assertEqual(sent['facts'],[{'relation':'chat_turn','args':['turn_0','user']},
                                        {'relation':'chat_turn','args':['turn_1','assistant']}])
        self.assertNotIn('evil',json.dumps(sent))
        self.assertEqual(receipt['history_sha256'],binding(HISTORY)['history_sha256'])
        self.assertEqual(receipt['evidence'][0]['message_sha256'],mork_v2.history_digest(HISTORY[0]))
        self.assertFalse(receipt['history_omitted'])

    def test_empty_history_still_calls_backend(self):
        selected,_=mork_v2.retrieve_history([],binding([]),PROFILE)
        self.assertEqual(selected,[])
        self.assertEqual(len(SyntheticBackend.calls),1)

    def test_missing_or_duplicate_native_rows_have_no_fallback(self):
        for transform in (lambda facts:[],lambda facts:[facts[0],facts[0]],
                          lambda facts:[facts[0],{'relation':'chat_turn','args':['unknown','assistant']}],
                          lambda facts:[facts[0],{'relation':'chat_turn','args':['turn_1','user']}]):
            SyntheticBackend.transform=staticmethod(transform)
            with self.assertRaises(ValueError):mork_v2.retrieve_history(HISTORY,binding(HISTORY),PROFILE)

    def test_native_failure_propagates(self):
        def fail(_):raise RuntimeError('Synthetic native failure')
        SyntheticBackend.transform=staticmethod(fail)
        with self.assertRaisesRegex(RuntimeError,'Synthetic native failure'):
            mork_v2.retrieve_history(HISTORY,binding(HISTORY),PROFILE)

    def test_receipt_runtime_and_cleanup_are_required(self):
        original=SyntheticBackend.query_facts
        for key,value in [('runtime_manifest_sha256','wrong'),('descendants_cleaned',False),
                          ('authorizes_actions',True)]:
            def changed(backend,*args,**kwargs):
                result=original(backend,*args,**kwargs);result[key]=value;return result
            with patch.object(SyntheticBackend,'query_facts',changed):
                with self.assertRaisesRegex(ValueError,'receipt mismatch'):
                    mork_v2.retrieve_history(HISTORY,binding(HISTORY),PROFILE)

    def test_revision_and_digest_bind_before_native_call(self):
        for key,value in [('revision',0),('history_sha256','changed'),('request_id','../../path')]:
            b=binding(HISTORY);b[key]=value
            with self.assertRaises(ValueError):mork_v2.retrieve_history(HISTORY,b,PROFILE)
        self.assertEqual(SyntheticBackend.calls,[])

    def test_exact_complete_utf8_bounded_history(self):
        for h in (HISTORY[:1],HISTORY*5,[HISTORY[1],HISTORY[0]],
                  [{'role':'user','content':'λ'*2049},HISTORY[1]]):
            with self.assertRaises(ValueError):mork_v2.retrieve_history(h,binding(h),PROFILE)
        self.assertEqual(SyntheticBackend.calls,[])

    def test_mutation_during_retrieval_is_rejected(self):
        h=copy.deepcopy(HISTORY)
        def mutate(facts):
            h[0]['content']='changed after claim'
            return facts
        SyntheticBackend.transform=staticmethod(mutate)
        with self.assertRaisesRegex(ValueError,'changed during'):
            mork_v2.retrieve_history(h,binding(h),PROFILE)


@unittest.skipUnless(os.environ.get('ROKO_MORK_V2_TEST_PROFILE'),'Requires qualified external native MORK')
class MorkV2NativeTests(unittest.TestCase):
    def test_real_empty_and_complete_history(self):
        profile=json.loads(Path(os.environ['ROKO_MORK_V2_TEST_PROFILE']).read_text())
        for history in ([],HISTORY):
            selected,receipt=mork_v2.retrieve_history(history,binding(history),profile)
            self.assertEqual(selected,history)
            self.assertTrue(receipt['native']['network_denied'])
            self.assertTrue(receipt['native']['descendants_cleaned'])
            self.assertNotIn('synthetic_test_only',receipt['native'])


if __name__=='__main__':unittest.main()
