"""Durable cognitive callback contracts using fake model/NARS execution only.

No test here claims native NARS, Omega, or Granite inference. Actual request
extraction and SQLite transactions run; the supplied runner is explicitly synthetic.
"""
import json
import hashlib
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
from cognition import NarsCognition
from recovered import system_message
from components.nars_hyperon.source.contract import canonical,independent_expected,response_from_rows

TEXT='A robin is a bird. A bird is an animal. What follows?'
CAT='A cat is a mammal. A mammal is an animal. What follows?'


class FakeProvider:
    def __init__(self):
        self.calls=0;self.messages=[];self.last_generation=None;self.last_error=None
        self.max_tokens=128;self.fail=False
    def chat(self,messages):
        self.calls+=1;self.messages.append(messages)
        if self.fail:
            self.last_error='native_turn_failed'
            raise RuntimeError('Synthetic model failure; no native call')
        self.last_generation={'input_tokens':20,'output_tokens':3,'finish_reason':'eos'}
        return 'Synthetic model answer.'


class FakeNarsRunner:
    def __init__(self):self.calls=[];self.directories=[];self.starts=[]
    def __call__(self,request,*,manifest,admission,evidence_directory):
        # Match the real runner's exclusive-directory behavior. The generated
        # payload is a unit-test oracle, never presented as native evidence.
        if evidence_directory.name!='native':raise AssertionError('Native output must have its own child directory')
        start=json.loads((evidence_directory.parent/'turn-start.json').read_text())
        if start['request']!=request or start['phase']!='prepared':raise AssertionError('Start record must predate native callback')
        if start['native_request_sha256']!=hashlib.sha256(canonical(request)).hexdigest():raise AssertionError('Start request digest mismatch')
        self.starts.append(start)
        evidence_directory.mkdir(parents=True,exist_ok=False)
        (evidence_directory/'SYNTHETIC_TEST_ONLY').write_text('No native inference')
        self.calls.append(request);self.directories.append(evidence_directory)
        rows=[{'subject_index':a,'predicate_index':b,'frequency':float(f),'confidence':float(c)}
              for (a,b),(f,c) in independent_expected(request).items()]
        return response_from_rows(request,rows),{'synthetic_test_only':True}


class DurableCognitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patch=patch.dict(os.environ,{'ROKO_HISTORY_DB':str(self.root/'history.sqlite')});self.patch.start()
        self.previous=conversation.session
        api.current=None;api.immediate=None;api.completed=None
        self.runner=FakeNarsRunner();self.provider=FakeProvider()
        self.start(self.provider,self.runner)
    def tearDown(self):
        if api.store:api.store.close()
        api.store=None;api.current=None;api.immediate=None;api.completed=None
        conversation.session=self.previous;self.patch.stop();self.temp.cleanup()
    def start(self,provider,runner):
        manifest=self.root/'synthetic-manifest.json';manifest.write_text('{}')
        reasoner=NarsCognition(manifest,'synthetic-test-only',self.root/'evidence',run=runner)
        api.initialize(provider,lambda *args,**kwargs:{'focus':[]},reasoner=reasoner)
    def request(self,**changes):
        value=dict(api_version=2,op='turn',session_id='one',request_id='r1',expected_revision=0,text=TEXT,context=[])
        value.update(changes);return value
    def prepare(self,**changes):return api.prepare_line(json.dumps(self.request(**changes)))
    def complete(self):
        session=conversation.session;messages=session.history+[session.user_message()]
        answer=session.infer(messages)
        return json.loads(session.commit(messages+[answer]))
    def snapshot(self,session='one'):return api.store.snapshot(session,include_cognition=True)
    def restart(self):
        api.store.close();self.provider=FakeProvider();self.runner=FakeNarsRunner()
        self.start(self.provider,self.runner)

    def test_restart_restores_cognitive_ledger_into_model_prompt(self):
        self.assertTrue(self.prepare());self.complete()
        old=self.snapshot();self.assertEqual(len(old['cognitive_history']),1)
        self.restart()
        self.assertTrue(self.prepare(request_id='r2',expected_revision=1,text='What creature did I mention?'))
        session=conversation.session
        self.assertEqual(session.cognitive_history,old['cognitive_history'])
        self.assertIn('robin -> animal',system_message(session))
        self.assertIn('Uncertain derived belief',system_message(session))
        self.complete()
        self.assertEqual(self.runner.calls,[])
        self.assertIn('robin -> animal',self.provider.messages[0][0]['content'])
        self.assertEqual(self.snapshot()['cognitive_history'],old['cognitive_history'])
        self.assertEqual(self.snapshot()['revision'],2)

    def test_saved_replay_after_restart_invokes_neither_runner_nor_provider(self):
        self.assertTrue(self.prepare());saved=self.complete();old=self.snapshot()
        self.restart()
        self.assertFalse(self.prepare());self.assertEqual(json.loads(api.immediate_json()),saved)
        self.assertEqual(self.runner.calls,[]);self.assertEqual(self.provider.calls,0)
        self.assertEqual(self.snapshot(),old)

    def test_stale_cas_does_not_invoke_nars_or_model(self):
        self.assertTrue(self.prepare());self.complete();old=self.snapshot()
        self.assertFalse(self.prepare(request_id='stale',text=CAT))
        self.assertEqual(json.loads(api.immediate_json())['code'],'stale_revision')
        self.assertEqual(len(self.runner.calls),1);self.assertEqual(self.provider.calls,1)
        self.assertEqual(self.snapshot(),old)

    def test_native_evidence_binds_session_request_and_claimed_revision(self):
        self.assertTrue(self.prepare())
        receipt=conversation.session.reasoner.receipts[-1]
        binding={'session_id':'one','request_id':'r1','revision':0}
        digest=hashlib.sha256(canonical(binding)).hexdigest()
        self.assertEqual(receipt['turn_binding'],binding)
        self.assertEqual(receipt['binding_sha256'],digest)
        self.assertEqual(receipt['prompt_context']['id'],'nars_'+digest)
        native=self.runner.directories[-1]
        self.assertEqual(native.name,'native')
        sidecar=json.loads((native.parent/'turn-binding.json').read_text())
        self.assertEqual(sidecar['turn_binding'],binding)
        self.assertEqual(sidecar['native_request_sha256'],hashlib.sha256(canonical(self.runner.calls[-1])).hexdigest())
        self.assertEqual(self.runner.calls[-1]['task_id'],'req_'+digest[:28])
        self.assertTrue(all(p['source'].endswith(';turn:'+digest) for p in self.runner.calls[-1]['premises']))
        first_native=canonical(self.runner.calls[-1])
        self.complete()
        self.assertTrue(self.prepare(session_id='two'))
        self.assertNotEqual(conversation.session.reasoner.receipts[-1]['binding_sha256'],digest)
        self.assertNotEqual(canonical(self.runner.calls[-1]),first_native)
        self.complete()

    def test_failed_request_successor_has_distinct_evidence_identity(self):
        self.assertTrue(self.prepare())
        first=conversation.session.reasoner.receipts[-1]['binding_sha256']
        first_request=canonical(self.runner.calls[-1])
        api.abort()
        self.assertTrue(self.prepare(request_id='retry-new-id'))
        receipt=conversation.session.reasoner.receipts[-1]
        self.assertNotEqual(receipt['binding_sha256'],first)
        self.assertEqual(receipt['turn_binding']['revision'],0)
        self.assertEqual(receipt['turn_binding']['request_id'],'retry-new-id')
        self.assertNotEqual(canonical(self.runner.calls[-1]),first_request)
        self.complete()

    def test_failed_model_preserves_prior_cognitive_ledger_and_history(self):
        self.assertTrue(self.prepare());self.complete();old=self.snapshot()
        self.provider.fail=True
        self.assertTrue(self.prepare(request_id='r2',expected_revision=1,text=CAT))
        self.assertEqual(len(conversation.session.pending_cognition),1)
        self.assertEqual(len(conversation.session.cognitive_context),2)
        with self.assertRaises(RuntimeError):self.complete()
        self.assertEqual(json.loads(api.abort())['code'],'native_turn_failed')
        self.assertEqual(self.snapshot(),old)
        self.assertEqual(conversation.session.cognitive_context,old['cognitive_history'])
        self.assertEqual(conversation.session.pending_cognition,[])
        self.restart()
        self.assertTrue(self.prepare(request_id='r3',expected_revision=1,text='What did I say?'))
        self.assertNotIn('cat -> animal',system_message(conversation.session))
        self.complete();self.assertEqual(self.snapshot()['cognitive_history'],old['cognitive_history'])

    def test_two_sessions_revision_one_have_independent_evidence_directories(self):
        self.assertTrue(self.prepare());self.complete()
        self.assertTrue(self.prepare(session_id='two',text=CAT));self.complete()
        self.assertEqual([r['revision'] for r in self.runner.calls],[1,1])
        self.assertEqual(len(set(self.runner.directories)),2)
        self.assertTrue(all(p.parent.name.startswith(r['binding_sha256']+'-')
            for p,r in zip(self.runner.directories,conversation.session.reasoner.receipts)))
        one=self.snapshot('one');two=self.snapshot('two')
        self.assertIn('robin -> animal',one['cognitive_history'][0]['text'])
        self.assertNotIn('robin -> animal',two['cognitive_history'][0]['text'])
        self.assertIn('cat -> animal',two['cognitive_history'][0]['text'])
        self.assertEqual(one['revision'],1);self.assertEqual(two['revision'],1)

    def test_supported_grammar_and_unsupported_prose_keep_distinct_paths(self):
        self.assertTrue(self.prepare());first=self.complete()
        self.assertEqual(len(self.runner.calls),1)
        for i,text in enumerate(('Hello, can we talk?','Maybe a robin is a bird. A bird is an animal.',
                                 'A robin is a bird. A bird is an animal. An animal is a thing.')):
            self.assertTrue(self.prepare(session_id='ordinary'+str(i),text=text))
            self.complete();self.assertEqual(self.snapshot('ordinary'+str(i))['cognitive_history'],[])
        self.assertEqual(len(self.runner.calls),1);self.assertEqual(self.provider.calls,4)
        self.assertEqual(first['context_ids'],[])
        self.assertNotIn('cognitive_history',api.store.snapshot('one'))
        self.assertNotIn('cognitive_observation_ids',first)

    def test_duplicate_new_observation_ids_cannot_invoke_model_or_commit(self):
        conversation.session.reasoner=lambda *_:[{'id':'duplicate','text':'One'},
                                                  {'id':'duplicate','text':'Two'}]
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(self.snapshot(),{'revision':0,'history':[],'pending':None,'cognitive_history':[]})
        self.assertEqual(conversation.session.pending_cognition,[])

    def test_observation_clash_with_committed_ledger_cannot_generate_or_commit(self):
        self.assertTrue(self.prepare());self.complete()
        prior=self.snapshot();old=dict(prior['cognitive_history'][0])
        conversation.session.reasoner=lambda *_:[dict(old,text='Changed belief with existing identity')]
        self.assertFalse(self.prepare(request_id='r2',expected_revision=1,text=CAT))
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
        self.assertEqual(self.provider.calls,1)
        self.assertEqual(self.snapshot(),prior)
        self.assertEqual(conversation.session.pending_cognition,[])
        self.assertEqual(conversation.session.cognitive_context,prior['cognitive_history'])

    def test_nars_timeout_retains_attempt_identity_but_not_history_or_model_output(self):
        directories=[]
        def timeout(request,**kwargs):
            attempt=kwargs['evidence_directory'].parent
            self.assertTrue((attempt/'turn-start.json').is_file())
            directories.append(attempt)
            raise TimeoutError('Synthetic callback timeout')
        conversation.session.reasoner.run=timeout
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(self.snapshot(),{'revision':0,'history':[],'pending':None,'cognitive_history':[]})
        start=json.loads((directories[0]/'turn-start.json').read_text())
        self.assertEqual(start['turn_binding'],{'session_id':'one','request_id':'r1','revision':0})
        self.assertFalse((directories[0]/'turn-binding.json').exists())
        self.assertFalse(self.prepare())
        self.assertEqual(json.loads(api.immediate_json())['code'],'failed')
        self.assertEqual(len(directories),1)


if __name__=='__main__':unittest.main()
