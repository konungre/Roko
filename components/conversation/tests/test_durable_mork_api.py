"""Durable/MORK callback boundary tests; all MORK/NARS/model calls are doubles."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
import conversation
import durable_api as api
import mork_v2


class ModelDouble:
    def __init__(self,events):
        self.profile={'mork_memory':{'manifest':'unused-test-path','manifest_sha256':'test-only'}}
        self.events=events
        self.mork_receipts=[]
        self.calls=0
        self.last_generation=None
        self.last_error=None
        self.max_tokens=128
        self.answer='A callback test answer.'

    def chat(self,messages):
        self.events.append('model')
        self.calls+=1
        self.last_generation={'input_tokens':20,'output_tokens':5,'finish_reason':'eos'}
        return self.answer


class DurableMorkApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.environment=patch.dict(os.environ,{'ROKO_HISTORY_DB':str(Path(self.temp.name)/'history.sqlite')})
        self.environment.start()
        self.previous=conversation.session
        api.current=api.immediate=api.completed=None
        self.events=[]
        self.nars_calls=[]
        self.observations=[{'id':'nars_turn_1','text':'Uncertain callback-only robin -> animal belief.'}]
        self.provider=ModelDouble(self.events)
        api.initialize(self.provider,lambda *a,**k:{'focus':[]},reasoner=self.reasoner)
        self.mork=patch.object(mork_v2,'retrieve_history',side_effect=self.retrieve)
        self.retrieve_mock=self.mork.start()

    def tearDown(self):
        api.store.close();api.store=None
        api.current=api.immediate=api.completed=None
        conversation.session=self.previous
        self.mork.stop();self.environment.stop();self.temp.cleanup()

    def reasoner(self,text,history):
        self.events.append('nars')
        self.nars_calls.append((text,history))
        return [dict(x) for x in self.observations] if not history else []

    def retrieve(self,history,binding,profile):
        # Observe the real durable claim before this deliberately fake retrieval.
        snapshot=api.store.snapshot(binding['session_id'])
        self.assertEqual(snapshot['pending'],binding['request_id'])
        self.assertEqual(snapshot['revision'],binding['revision'])
        self.assertEqual(snapshot['history'],history)
        self.assertEqual(binding['history_sha256'],mork_v2.history_digest(history))
        self.events.append('mork')
        return [dict(x) for x in history],{'test_double':True,'indexed_messages':len(history)}

    def request(self,**changes):
        value={'api_version':2,'op':'turn','session_id':'story','request_id':'r1',
               'expected_revision':0,'text':'A robin is a bird. A bird is an animal.','context':[]}
        value.update(changes);return value

    def prepare(self,**changes):
        return api.prepare_line(json.dumps(self.request(**changes)))

    def error(self):
        return json.loads(api.immediate_json())['code']

    def finish(self):
        # Callback exercise only: no Omega, native NARS, native MORK or model.
        session=conversation.session
        messages=session.history+[session.user_message()]
        assistant=session.infer(messages)
        return json.loads(session.commit(messages+[assistant]))

    def test_claim_precedes_mork_which_precedes_nars_and_model(self):
        self.assertTrue(self.prepare())
        self.assertEqual(self.events,['mork','nars'])
        result=self.finish()
        self.assertEqual(self.events,['mork','nars','model'])
        self.assertEqual(result['revision'],1)
        self.assertEqual(self.provider.mork_receipts,[{'test_double':True,'indexed_messages':0}])
        self.assertEqual(api.store.snapshot('story',include_cognition=True)['cognitive_history'],self.observations)

    def test_replay_and_stale_revision_do_not_call_mork_nars_or_model(self):
        self.assertTrue(self.prepare());saved=self.finish()
        before=list(self.events)
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json()),saved)
        self.assertFalse(self.prepare(request_id='stale'))
        self.assertEqual(self.error(),'stale_revision')
        self.assertFalse(self.prepare(text='Changed same ID'))
        self.assertEqual(self.error(),'request_conflict')
        self.assertEqual(self.events,before)
        self.assertEqual(self.retrieve_mock.call_count,1)
        self.assertEqual(len(self.nars_calls),1)
        self.assertEqual(self.provider.calls,1)

    def test_mork_failure_does_not_call_nars_or_model_or_commit(self):
        self.retrieve_mock.side_effect=ValueError('Explicit MORK test-double failure')
        self.assertFalse(self.prepare())
        self.assertEqual(self.error(),'native_turn_failed')
        self.assertEqual(self.retrieve_mock.call_count,1)
        self.assertEqual(self.nars_calls,[])
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(api.store.snapshot('story',include_cognition=True),
                         {'revision':0,'history':[],'pending':None,'cognitive_history':[]})
        self.assertFalse(self.prepare())
        self.assertEqual(self.error(),'failed')
        self.assertEqual(self.retrieve_mock.call_count,1)

    def test_eight_message_bound_is_explicit_and_runs_no_mork(self):
        for index in range(4):
            user={'role':'user','content':'User '+str(index)}
            assistant={'role':'assistant','content':'Assistant '+str(index)}
            claim=api.store.start('story','seed'+str(index),index,{'text':user['content']})
            api.store.commit(claim['token'],user,assistant,{'text':assistant['content']},
                             cognitive_history=self.observations)
        before=api.store.snapshot('story',include_cognition=True)
        self.assertEqual(conversation.session.max_history,8)
        self.assertFalse(self.prepare(request_id='fifth',expected_revision=4))
        self.assertEqual(self.error(),'history_limit')
        self.assertEqual(self.retrieve_mock.call_count,0)
        self.assertEqual(self.nars_calls,[])
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(api.store.snapshot('story',include_cognition=True),before)

    def test_fourth_exchange_is_admitted_and_commits_exactly_eight_messages(self):
        for index in range(3):
            user={'role':'user','content':'User '+str(index)}
            assistant={'role':'assistant','content':'Assistant '+str(index)}
            c=api.store.start('story','seed'+str(index),index,{'text':user['content']})
            api.store.commit(c['token'],user,assistant,{'text':assistant['content']},
                             cognitive_history=self.observations)
        self.assertTrue(self.prepare(request_id='fourth',expected_revision=3))
        self.assertEqual(self.retrieve_mock.call_args.args[0],api.store.snapshot('story')['history'])
        result=self.finish()
        self.assertEqual(result['revision'],4)
        self.assertEqual(len(api.store.snapshot('story')['history']),8)
        self.assertEqual(api.store.snapshot('story',include_cognition=True)['cognitive_history'],self.observations)

    def test_cognitive_ledger_survives_restart_replay_and_failed_mork(self):
        self.assertTrue(self.prepare());saved=self.finish()
        before=api.store.snapshot('story',include_cognition=True)
        api.store.close();self.events.clear();self.nars_calls.clear()
        self.provider=ModelDouble(self.events)
        api.initialize(self.provider,lambda *a,**k:{'focus':[]},reasoner=self.reasoner)
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json()),saved)
        self.assertEqual(self.events,[])
        self.retrieve_mock.reset_mock()
        self.retrieve_mock.side_effect=ValueError('MORK test-double unavailable after restart')
        self.assertFalse(self.prepare(request_id='r2',expected_revision=1))
        self.assertEqual(self.error(),'native_turn_failed')
        self.assertEqual(self.retrieve_mock.call_count,1)
        self.assertEqual(conversation.session.cognitive_history,self.observations)
        self.assertEqual(api.store.snapshot('story',include_cognition=True),before)
        self.assertEqual(self.nars_calls,[])
        self.assertEqual(self.provider.calls,0)
        self.retrieve_mock.side_effect=self.retrieve
        self.assertTrue(self.prepare(request_id='r3',expected_revision=1))
        self.assertEqual(conversation.session.cognitive_context,self.observations)
        self.finish()
        self.assertEqual(api.store.snapshot('story',include_cognition=True)['cognitive_history'],self.observations)

    def test_message_byte_limit_fails_before_mork_or_reasoning(self):
        self.assertFalse(self.prepare(text='é'*2200))
        self.assertEqual(self.error(),'invalid_request')
        self.assertEqual(self.retrieve_mock.call_count,0)
        self.assertEqual(self.nars_calls,[])
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(api.store.snapshot('story')['revision'],0)

    def test_nars_runtime_failure_is_native_failure_and_preserves_prior_ledger(self):
        self.assertTrue(self.prepare());self.finish()
        before=api.store.snapshot('story',include_cognition=True)
        self.events.clear()
        def failing_reasoner(text,history):
            self.events.append('nars_failure')
            raise RuntimeError('Explicit NARS test-double runtime failure')
        conversation.session.reasoner=failing_reasoner
        self.assertFalse(self.prepare(request_id='r2',expected_revision=1))
        self.assertEqual(self.error(),'native_turn_failed')
        self.assertEqual(self.events,['mork','nars_failure'])
        self.assertEqual(self.provider.calls,1)
        self.assertEqual(api.store.snapshot('story',include_cognition=True),before)
        self.assertFalse(self.prepare(request_id='r2',expected_revision=1))
        self.assertEqual(self.error(),'failed')
        self.assertEqual(self.events,['mork','nars_failure'])

    def test_oversized_model_reply_cannot_enter_mork_history(self):
        self.assertTrue(self.prepare())
        self.provider.answer='é'*2200
        with self.assertRaises(ValueError):self.finish()
        json.loads(api.abort())
        self.assertEqual(api.store.snapshot('story',include_cognition=True),
                         {'revision':0,'history':[],'pending':None,'cognitive_history':[]})


if __name__=='__main__':unittest.main()
