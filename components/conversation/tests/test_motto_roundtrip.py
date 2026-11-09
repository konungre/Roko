"""Real Hyperon/Motto with synthetic model replies and actual durable SQLite API."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(SOURCE.parent/'motto_conversation'))
import conversation
import durable_api as api
from adapter import chat


@unittest.skipUnless(importlib.util.find_spec('hyperon'),'requires actual Hyperon runtime')
class DurableRoundTripTests(unittest.TestCase):
    def test_incompatible_model_output_cannot_poison_next_request(self):
        class SyntheticProvider:
            last_error=None
            last_generation=None
            def __init__(self):self.calls=0
            def chat(self,messages):
                def model(_):
                    self.calls+=1
                    self.last_generation={'input_tokens':20,'output_tokens':4,'finish_reason':'eos'}
                    return r'line\nnext' if self.calls==1 else 'Safe actual\nnewline.'
                return chat(messages,model)
        old_session=conversation.session
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,ROKO_HISTORY_DB=str(Path(directory)/'history.sqlite')):
            provider=SyntheticProvider();api.current=None;api.immediate=None;api.completed=None
            api.initialize(provider,lambda *a,**k:{'focus':[]})
            def request(identifier):
                return json.dumps(dict(api_version=2,op='turn',session_id='s',request_id=identifier,
                                       expected_revision=0,text='Hello',context=[]))
            try:
                self.assertTrue(api.prepare_line(request('bad')))
                session=conversation.session
                with self.assertRaises(ValueError):
                    session.infer(session.history+[session.user_message()])
                self.assertEqual(json.loads(api.abort())['status'],'error')
                self.assertEqual(api.store.snapshot('s')['revision'],0)
                self.assertEqual(api.store.snapshot('s')['history'],[])
                self.assertTrue(api.prepare_line(request('retry')))
                messages=session.history+[session.user_message()]
                answer=session.infer(messages)
                saved=json.loads(session.commit(messages+[answer]))
                self.assertEqual(saved['status'],'completed');self.assertEqual(saved['revision'],1)
                self.assertEqual(len(api.store.snapshot('s')['history']),2)
                self.assertFalse(api.prepare_line(request('retry')))
                self.assertEqual(json.loads(api.immediate_json()),saved)
                self.assertEqual(provider.calls,2)
            finally:
                api.store.close();api.store=None;api.current=None;api.immediate=None;api.completed=None
                conversation.session=old_session


if __name__=='__main__':unittest.main()
