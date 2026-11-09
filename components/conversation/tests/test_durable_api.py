"""Callback-level durable API tests with an explicit fake provider, no native claims."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
import conversation
import durable_api as api
from fresh import GenerationError


class FakeProvider:
    def __init__(self):
        self.calls = 0
        self.max_tokens = 128
        self.last_generation = None
        self.last_error = None
        self.finish_reason = 'eos'
        self.raise_code = None
        self.messages = []

    def chat(self, messages):
        self.calls += 1
        self.messages.append(messages)
        if self.raise_code:
            self.last_error = self.raise_code
            raise GenerationError(self.raise_code)
        self.last_generation = {'input_tokens':20,
                                'output_tokens':self.max_tokens if self.finish_reason=='length' else 3,
                                'finish_reason':self.finish_reason}
        return 'A test answer.'


class DurableApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.dict(os.environ,{'ROKO_HISTORY_DB':str(Path(self.temp.name)/'history.sqlite')})
        self.patch.start()
        self.previous=conversation.session
        api.current=None
        api.immediate=None
        api.completed=None
        self.provider=FakeProvider()
        api.initialize(self.provider,lambda *args,**kwargs: {'focus':[]})

    def tearDown(self):
        if api.store:
            api.store.close()
        api.store=None
        api.current=None
        api.immediate=None
        api.completed=None
        conversation.session=self.previous
        self.patch.stop()
        self.temp.cleanup()

    def request(self, **changes):
        value={'api_version':2,'op':'turn','session_id':'session','request_id':'r1',
               'expected_revision':0,'text':'Remember a lighthouse.','context':[]}
        value.update(changes)
        return value

    def prepare(self, **changes):
        return api.prepare_line(json.dumps(self.request(**changes)))

    def immediate(self):
        return json.loads(api.immediate_json())

    def fake_complete(self):
        # Exercise the Python callback contract only. No Omega/native inference.
        session=conversation.session
        messages=session.history+[session.user_message()]
        assistant=session.infer(messages)
        result=json.loads(session.commit(messages+[assistant]))
        self.assertEqual(result,json.loads(api.completed_json()))
        return result

    def test_replay_does_not_repeat_provider_and_stale_cas_does_not_infer(self):
        self.assertTrue(self.prepare())
        saved=self.fake_complete()
        self.assertEqual(self.provider.calls,1)
        self.assertFalse(self.prepare())
        self.assertEqual(self.immediate(),saved)
        self.assertEqual(self.provider.calls,1)
        self.assertFalse(self.prepare(request_id='r2'))
        self.assertEqual(self.immediate()['code'],'stale_revision')
        self.assertEqual(self.provider.calls,1)
        self.assertEqual(api.store.snapshot('session')['revision'],1)

    def test_same_id_with_changed_payload_is_conflict(self):
        self.assertTrue(self.prepare());self.fake_complete()
        self.assertFalse(self.prepare(text='Changed request'))
        self.assertEqual(self.immediate()['code'],'request_conflict')
        self.assertEqual(self.provider.calls,1)

    def test_partial_reply_is_explicit_durable_and_replayable(self):
        self.provider.finish_reason='length'
        self.assertTrue(self.prepare(max_output_tokens=1))
        saved=self.fake_complete()
        self.assertEqual(saved['status'],'truncated')
        self.assertEqual(saved['generation'],{'input_tokens':20,'output_tokens':1,'finish_reason':'length'})
        self.assertEqual(saved['history_policy'],'complete_no_omission')
        self.assertEqual(saved['executed_actions'],0)
        self.assertEqual(saved['revision'],1)
        self.assertEqual(api.store.snapshot('session')['history'][-1]['content'],saved['text'])
        self.assertFalse(self.prepare(max_output_tokens=1))
        self.assertEqual(self.immediate(),saved)
        self.assertEqual(self.provider.calls,1)

    def test_aborted_inference_never_commits_and_new_request_can_continue(self):
        self.provider.raise_code='context_limit'
        self.assertTrue(self.prepare())
        with self.assertRaises(GenerationError):self.fake_complete()
        aborted=json.loads(api.abort())
        self.assertEqual(aborted['code'],'context_limit')
        self.assertEqual(api.store.snapshot('session'),{'revision':0,'history':[],'pending':None})
        self.assertFalse(self.prepare())
        self.assertEqual(self.immediate()['code'],'failed')
        self.assertEqual(self.provider.calls,1)
        self.provider.raise_code=None
        self.assertTrue(self.prepare(request_id='r2'))
        saved=self.fake_complete()
        self.assertEqual(saved['revision'],1)
        self.assertEqual(self.provider.calls,2)
        self.assertEqual(len(api.store.snapshot('session')['history']),2)

    def test_restart_loads_complete_history_and_replays_without_model(self):
        self.assertTrue(self.prepare());saved=self.fake_complete()
        api.store.close()
        replacement=FakeProvider()
        api.initialize(replacement,lambda *args,**kwargs:{'focus':[]})
        self.assertFalse(self.prepare())
        self.assertEqual(self.immediate(),saved)
        self.assertEqual(replacement.calls,0)
        self.assertTrue(self.prepare(request_id='r2',expected_revision=1,text='What did I mention?'))
        self.assertEqual(conversation.session.history,api.store.snapshot('session')['history'])
        self.assertEqual(len(conversation.session.history),2)
        second=self.fake_complete()
        self.assertEqual(second['revision'],2)
        self.assertEqual(len(api.store.snapshot('session')['history']),4)
        self.assertEqual(replacement.messages[0][1]['content'],'Remember a lighthouse.')

    def test_duplicate_unknown_and_malformed_fields_do_not_claim_or_infer(self):
        valid=json.dumps(self.request())
        bad_lines=['not JSON','[]',valid.replace('"api_version": 2','"api_version": 2, "api_version": 2'),
                   json.dumps(self.request(extra='not allowed')),json.dumps(self.request(api_version=True)),
                   json.dumps(self.request(max_output_tokens=True)),json.dumps(self.request(max_output_tokens=129)),
                   json.dumps({k:v for k,v in self.request().items() if k!='context'})]
        for line in bad_lines:
            self.assertFalse(api.prepare_line(line),line)
            self.assertEqual(self.immediate()['code'],'invalid_request')
            self.assertEqual(api.store.snapshot('session'),{'revision':0,'history':[],'pending':None})
        self.assertEqual(self.provider.calls,0)

    def test_invalid_context_after_claim_fails_without_history(self):
        self.assertFalse(self.prepare(context=[{'id':'bad'}]))
        self.assertEqual(self.immediate()['code'],'invalid_request')
        self.assertEqual(api.store.snapshot('session'),{'revision':0,'history':[],'pending':None})
        self.assertEqual(self.provider.calls,0)
        self.assertFalse(self.prepare(request_id='r2',context=[{'id':'x','text':'x','sti':True,'lti':0,'stimulus':0}]))
        self.assertEqual(api.store.snapshot('session')['revision'],0)

    def test_completed_guard_refuses_uncommitted_or_previous_turn_result(self):
        self.assertTrue(self.prepare())
        with self.assertRaises(ValueError):api.completed_json()
        first=self.fake_complete()
        self.assertEqual(first,json.loads(api.completed_json()))
        self.assertTrue(self.prepare(request_id='r2',expected_revision=1))
        with self.assertRaises(ValueError):api.completed_json()
        json.loads(api.abort())
        with self.assertRaises(ValueError):api.completed_json()
        self.assertEqual(api.store.snapshot('session')['revision'],1)

    def test_snapshot_is_read_only_and_native_failure_after_prior_turn_preserves_it(self):
        self.assertTrue(self.prepare());saved=self.fake_complete()
        snapshot_packet={'api_version':2,'op':'snapshot','session_id':'session'}
        self.assertFalse(api.prepare_line(json.dumps(snapshot_packet)))
        snapshot=self.immediate()
        self.assertEqual(snapshot['status'],'snapshot')
        self.assertEqual(snapshot['revision'],1)
        self.provider.raise_code='native_turn_failed'
        self.assertTrue(self.prepare(request_id='r2',expected_revision=1))
        with self.assertRaises(GenerationError):self.fake_complete()
        json.loads(api.abort())
        self.assertEqual(api.store.snapshot('session')['history'],snapshot['history'])
        self.assertEqual(api.store.snapshot('session')['revision'],1)


if __name__=='__main__':unittest.main()
