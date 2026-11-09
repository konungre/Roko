"""AI-DSL cognitive task boundaries; native execution is a separate probe."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import conversation
import durable_api as api
from learning import validate_tasks,observation

REQUEST={'version':1,'goal':'speech_emotion','depth':4}
TASKS=[{'component':'ai_dsl','request':REQUEST}]


class TaskTests(unittest.TestCase):
    def test_ai_dsl_is_closed_bounded_data(self):
        self.assertEqual(validate_tasks(TASKS),TASKS)
        for request in ({**REQUEST,'depth':5},{**REQUEST,'goal':'shell'},{**REQUEST,'code':'!(shell x)'}):
            with self.assertRaises(ValueError):validate_tasks([{'component':'ai_dsl','request':request}])

    def test_projection_does_not_claim_services_ran(self):
        text=observation('ai_dsl',{'goal':'speech_emotion','accepted':[{}],'rejected':[{}]})
        self.assertLessEqual(len(text),500)
        self.assertIn('executed_services=0',text)

    def test_actual_durable_api_records_and_replays_synthetic_search_result(self):
        result={'fixture_only':True,'executed_services':0}
        class Learner:
            calls=0
            def run_turn(self,tasks,text,history,binding):
                self.calls+=1
                return {'observations':[{'id':'ai_dsl_fixture','text':'Synthetic search result; no services ran.'}],
                    'results':[{'component':'ai_dsl','observation_id':'ai_dsl_fixture','result':result}]}
        class Provider:
            last_error=None;last_generation=None
            def __init__(self):self.learning=Learner();self.calls=0
            def chat(self,messages):
                self.calls+=1;self.last_generation={'input_tokens':30,'output_tokens':4,'finish_reason':'eos'}
                return 'Synthetic answer.'
        previous=conversation.session
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,ROKO_HISTORY_DB=str(Path(directory)/'history.sqlite')):
            provider=Provider();api.current=None;api.initialize(provider,lambda *a,**k:{'focus':[]})
            request=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='Explain.',context=[],cognitive_tasks=TASKS)
            try:
                self.assertTrue(api.prepare_line(json.dumps(request)))
                session=conversation.session;messages=session.history+[session.user_message()]
                answer=session.infer(messages);saved=json.loads(session.commit(messages+[answer]))
                self.assertEqual(saved['cognitive_results'][0]['result'],result)
                self.assertEqual(len(api.store.snapshot('s',include_cognition=True)['cognitive_history']),1)
                self.assertFalse(api.prepare_line(json.dumps(request)))
                self.assertEqual(json.loads(api.immediate_json()),saved)
                self.assertEqual(provider.calls,1);self.assertEqual(provider.learning.calls,1)
                changed={**request,'cognitive_tasks':[{'component':'ai_dsl','request':{**REQUEST,'depth':3}}]}
                self.assertFalse(api.prepare_line(json.dumps(changed)))
                self.assertEqual(json.loads(api.immediate_json())['code'],'request_conflict')
            finally:
                api.store.close();api.store=None;api.current=None;api.immediate=None;api.completed=None
                conversation.session=previous


if __name__=='__main__':unittest.main()
