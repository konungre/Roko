"""Typed component/v2 contracts; fake learner outputs are never native evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import conversation
import durable_api as api
from learning import validate_tasks,observation

META={'version':1,'request_id':'fixture','operation':'rank_proposals',
      'state':{'goals':[.5]*8,'modulators':[.5]*6},
      'candidates':[{'id':'first','correlations':[.1]*8,'risk':.1,'delta_goals':[0]*8}]}
TASKS=[{'component':'metamo','request':META}]

class FakeLearning:
    def __init__(self):self.calls=[];self.fail=False
    def run_turn(self,tasks,text,history,binding):
        self.calls.append(copy.deepcopy((tasks,text,history,binding)))
        if self.fail:raise RuntimeError('Synthetic component failure')
        obs={'id':'metamo_'+binding['session_id']+'_'+binding['request_id'],
             'text':'METAMO synthetic test observation; no native execution.'}
        return {'observations':[obs],'results':[{'component':'metamo','observation_id':obs['id'],'result':{'synthetic_test_only':True}}]}

class Provider:
    def __init__(self):self.learning=FakeLearning();self.calls=0;self.last_error=None;self.last_generation=None
    def chat(self,messages):
        self.calls+=1;self.messages=messages
        self.last_generation={'input_tokens':20,'output_tokens':3,'finish_reason':'eos'}
        return 'Synthetic answer.'

class LearningV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=conversation.session
        self.env=patch.dict(os.environ,ROKO_HISTORY_DB=str(Path(self.temp.name)/'history.sqlite'));self.env.start()
        api.current=None;api.immediate=None;api.completed=None
        self.provider=Provider();api.initialize(self.provider,lambda *a,**k:{'focus':[]})
    def tearDown(self):
        api.store.close();api.store=None;api.current=None;conversation.session=self.old
        self.env.stop();self.temp.cleanup()
    def request(self,**changes):
        data=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,
            text='Explain the selection.',context=[],cognitive_tasks=copy.deepcopy(TASKS))
        data.update(changes);return data
    def prepare(self,**changes):return api.prepare_line(json.dumps(self.request(**changes)))
    def finish(self):
        s=conversation.session;messages=s.history+[s.user_message()];answer=s.infer(messages)
        return json.loads(s.commit(messages+[answer]))
    def test_real_api_atomic_commit_and_replay_skip_fake_components(self):
        self.assertTrue(self.prepare());response=self.finish()
        task,text,history,binding=self.provider.learning.calls[0]
        self.assertEqual(task,TASKS);self.assertEqual(binding,dict(session_id='s',request_id='r',revision=0))
        self.assertIn('METAMO synthetic',self.provider.messages[0]['content'])
        before=api.store.snapshot('s',include_cognition=True);self.assertEqual(len(before['cognitive_history']),1)
        self.assertFalse(self.prepare());self.assertEqual(json.loads(api.immediate_json()),response)
        self.assertEqual(len(self.provider.learning.calls),1);self.assertEqual(self.provider.calls,1)
    def test_changed_task_payload_cannot_reuse_request_id(self):
        self.assertTrue(self.prepare());self.finish()
        changed=copy.deepcopy(TASKS);changed[0]['request']['candidates'][0]['risk']=.5
        self.assertFalse(self.prepare(cognitive_tasks=changed))
        self.assertEqual(json.loads(api.immediate_json())['code'],'request_conflict')
        self.assertEqual(len(self.provider.learning.calls),1)
    def test_component_failure_does_not_commit_history_or_ledger(self):
        self.provider.learning.fail=True
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
        self.assertEqual(api.store.snapshot('s',include_cognition=True),dict(revision=0,history=[],pending=None,cognitive_history=[]))
        self.assertEqual(self.provider.calls,0)
    def test_unqualified_profile_is_fail_closed(self):
        self.provider.learning=None
        self.assertFalse(self.prepare());self.assertEqual(self.provider.calls,0)
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
    def test_invalid_tasks_do_not_claim(self):
        for value in ({},[{'component':'shell','request':{}}],TASKS*2,
                      [{'component':'metamo','request':{}}],[{**TASKS[0],'command':'evil'}]):
            with self.subTest(value=value):
                self.assertFalse(self.prepare(cognitive_tasks=value))
                self.assertEqual(json.loads(api.immediate_json())['code'],'invalid_request')
                self.assertEqual(api.store.snapshot('s')['revision'],0)
        self.assertEqual(self.provider.learning.calls,[])
    def test_truncated_model_response_retains_exact_structured_results(self):
        self.assertTrue(self.prepare())
        session=conversation.session;messages=session.history+[session.user_message()]
        answer=session.infer(messages)
        self.provider.last_generation={'input_tokens':20,'output_tokens':1,'finish_reason':'length'}
        saved=json.loads(session.commit(messages+[answer]))
        self.assertEqual(saved['status'],'truncated')
        self.assertEqual(saved['cognitive_results'][0]['result'],{'synthetic_test_only':True})
        self.assertFalse(self.prepare());self.assertEqual(json.loads(api.immediate_json()),saved)
        self.assertEqual(len(self.provider.learning.calls),1)

    def test_native_results_are_saved_and_replayed_separately_from_model_text(self):
        self.assertTrue(self.prepare());reply=self.finish()
        self.assertEqual(reply['text'],'Synthetic answer.')
        self.assertEqual(reply['cognitive_results'][0]['result'],{'synthetic_test_only':True})
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json())['cognitive_results'],reply['cognitive_results'])

if __name__=='__main__':unittest.main()
