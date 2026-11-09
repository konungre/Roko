"""Ordinary-turn receipt context: real SQLite/files, explicit native-query doubles."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import conversation
import durable_api as api
import package_awareness as awareness
from cognition import write_record
from components.os_atomspace import conversation_gateway as gateway
from context_summary import build_summary,SummaryBudgetError
from recovered import system_message
from types import SimpleNamespace


class ReceiptCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.manifest=root/'manifest.json';self.manifest.write_text(json.dumps({'source_commit':'a'*40}))
        profile={'package_awareness':{'manifest':str(self.manifest),'sha256':awareness.sha(self.manifest),'evidence_root':str(root/'evidence')}}
        with patch.object(awareness,'validate_profile'):
            self.observer=awareness.PackageAwareness(profile)
        self.packet={'facts':[{'phase':'observed','value':{'operation':'rollback'}}],'sequence':3,'machine':'fixture'}
        snapshot=hashlib.sha256(awareness.canonical(self.packet)).hexdigest()
        self.result={'snapshot_sha256':snapshot,'latest_observation':self.packet['facts'][0],
            'source_revision':3,'machine':'fixture','source_commit':'a'*40,
            **{key:False for key in ('mutation_authority','current_host_state_established','system_activation_established',
               'running_system_established','health_established','native_nix_reexecuted_here','producer_authenticated')}}
    def tearDown(self):self.temp.cleanup()
    def query(self,request,manifest,directory):
        directory.mkdir();receipt={'status':'passed','fixture_only':True}
        write_record(directory/'receipt.json',receipt)
        return copy.deepcopy(self.result),receipt
    def stage(self,request_id='r',revision=0,history=None):
        return self.observer.stage({'session_id':'s','request_id':request_id,'revision':revision},history or [])
    def test_native_query_is_cached_but_each_turn_is_bound(self):
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=self.query) as query:
            first=self.stage()
            second=self.stage('next',1,[{'role':'user','content':'hi'},{'role':'assistant','content':'hello'}])
            self.assertEqual(query.call_count,1)
            self.assertFalse(first['state']['query_reused']);self.assertTrue(second['state']['query_reused'])
            self.assertEqual(first['context'],second['context'])
            self.assertEqual(second['state']['binding']['request_id'],'next')
            first['state']['source']['machine']='mutated client copy'
            self.assertEqual(self.observer.cache['result']['machine'],'fixture')
    def test_changed_cached_receipt_fails_before_context_return(self):
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=self.query):
            self.stage();self.observer.cache['receipt_path'].write_text('{}')
            with self.assertRaises(ValueError):self.stage('next')
        self.assertEqual(self.observer.receipts[-1]['status'],'failed')
    def test_source_manifest_drift_fails_without_query(self):
        self.manifest.write_text('{}')
        with patch.object(gateway,'run') as query,self.assertRaises(ValueError):self.stage()
        query.assert_not_called()
    def test_incorrect_authority_result_is_not_cached(self):
        self.result['running_system_established']=True
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=self.query),self.assertRaises(ValueError):self.stage()
        self.assertIsNone(self.observer.cache)


class OrdinaryTurnTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,ROKO_HISTORY_DB=str(Path(self.temp.name)/'history.sqlite'));self.env.start()
        self.old=conversation.session;api.current=None
        class FakeAwareness:
            calls=0;fail=False
            def stage(self,binding,history):
                self.calls+=1
                if self.fail:raise ValueError('synthetic source drift')
                return {'context':[{'id':'package_fixture','text':'Imported fixture receipt; no running-system authority.'}],
                    'state':{'observation_id':'package_fixture','binding':binding,'fixture_only':True,'mutation_authority':False,'executed_actions':0}}
        class Provider:
            profile={'package_awareness':{'fixture_only':True}}
            last_error=None;last_generation=None;calls=0
            def __init__(self):self.package_awareness=FakeAwareness()
            def chat(self,messages):
                self.calls+=1;self.messages=messages;self.last_generation={'input_tokens':20,'output_tokens':3,'finish_reason':'eos'}
                return 'Synthetic answer.'
        self.provider=Provider();api.initialize(self.provider,lambda *a,**k:{'focus':[]})
    def tearDown(self):
        api.store.close();api.store=None;api.current=None;api.immediate=None;api.completed=None
        conversation.session=self.old;self.env.stop();self.temp.cleanup()
    def request(self,rid='r'):
        return json.dumps({'api_version':2,'op':'turn','session_id':'s','request_id':rid,'expected_revision':0,'text':'What package receipt is available?','context':[]})
    def test_plain_request_gets_receipt_atomically_and_replay_skips_awareness(self):
        self.assertTrue(api.prepare_line(self.request()))
        session=conversation.session;messages=session.history+[session.user_message()]
        answer=session.infer(messages);saved=json.loads(session.commit(messages+[answer]))
        self.assertIn('package_state',saved)
        self.assertIn('Imported fixture receipt',self.provider.messages[0]['content'])
        snapshot=api.store.snapshot('s',include_cognition=True)
        self.assertEqual(snapshot['revision'],1);self.assertEqual(snapshot['cognitive_history'],[])
        self.assertFalse(api.prepare_line(self.request()));self.assertEqual(json.loads(api.immediate_json()),saved)
        self.assertEqual(self.provider.package_awareness.calls,1);self.assertEqual(self.provider.calls,1)
    def test_source_failure_leaves_authoritative_history_unchanged(self):
        self.provider.package_awareness.fail=True
        self.assertFalse(api.prepare_line(self.request()))
        self.assertEqual(json.loads(api.immediate_json())['code'],'native_turn_failed')
        self.assertEqual(api.store.snapshot('s')['history'],[]);self.assertEqual(self.provider.calls,0)
        self.assertEqual(conversation.session.package_context,[])
    def test_extractive_context_keeps_receipt_and_does_not_rewrite_history(self):
        package=[{'id':'receipt','text':'PINNED_IMPORTED_RECEIPT'}]
        history=[{'role':'user','content':'old '*50},{'role':'assistant','content':'old answer'}]
        before=copy.deepcopy(history)
        messages,_=build_summary(history,'current',count_tokens=len,budget=10000,package_context=package)
        self.assertIn('PINNED_IMPORTED_RECEIPT',messages[0]['content']);self.assertEqual(history,before)
        counted=[]
        def too_large(prompt):counted.append(prompt);return 513
        with self.assertRaises(SummaryBudgetError):build_summary(history,'current',count_tokens=too_large,package_context=package)
        self.assertTrue(all('PINNED_IMPORTED_RECEIPT' in prompt for prompt in counted))
