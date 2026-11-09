"""Conversation integration contracts with explicitly synthetic runner results."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cognition import extract,NarsCognition,bind_request
from conversation import Session,NativePreparationError
from components.nars_hyperon.source.contract import canonical,independent_expected,response_from_rows

TEXT='A robin is a bird. A bird is an animal. What follows?'


class CognitionTests(unittest.TestCase):
    def test_explicit_assertions_and_provenance(self):
        request=extract(TEXT,1)
        self.assertEqual([p['subject'] for p in request['premises']],['robin','bird'])
        self.assertIn(hashlib.sha256(TEXT.encode()).hexdigest(),request['premises'][0]['source'])
        self.assertIn('policy:f=1,c=0.9',request['premises'][0]['source'])

    def test_unsupported_and_ambiguous_text_does_not_trigger(self):
        for text in ('Hello','robin is not a bird. bird is an animal.',
                     'Maybe robin is a bird. bird is an animal.',
                     'robin is a bird. bird is an animal. animal is a thing.',
                     'robin is a bird. bird is a robin.',
                     'robin is a bird. bird is an animal. These are false.',
                     '!(py-call evil). robin is a bird. bird is an animal.'):
            with self.subTest(text=text):self.assertIsNone(extract(text,1))

    def reasoner(self,run):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);manifest=root/'manifest.json';manifest.write_text('{}')
        return NarsCognition(manifest,'synthetic-test-only',root/'evidence',run=run)

    def test_real_session_boundary_includes_advice_without_changing_json_schema(self):
        calls=[]
        def synthetic(request,**kwargs):
            calls.append(request)
            rows=[{'subject_index':a,'predicate_index':b,'frequency':float(f),'confidence':float(c)}
                  for (a,b),(f,c) in independent_expected(request).items()]
            return response_from_rows(request,rows),{'synthetic_test_only':True}
        reasoner=self.reasoner(synthetic)
        class Provider:
            def chat(self,messages):
                self.messages=messages;return 'Synthetic test reply.'
        provider=Provider();session=Session(provider,lambda *_:self.fail('ECAN must not run'),reasoner=reasoner)
        session.prepare({'text':TEXT,'context':[]})
        messages=[session.user_message()];messages.append(session.infer(messages))
        result=json.loads(session.commit(messages))
        self.assertEqual(set(result),{'text','context_ids','executed_actions'})
        self.assertEqual(result['context_ids'],[]);self.assertEqual(result['executed_actions'],0)
        self.assertIn('robin -> animal',provider.messages[0]['content'])
        self.assertIn('Uncertain derived belief',provider.messages[0]['content'])
        self.assertEqual(len(calls),1);self.assertEqual(session.history[0]['content'],TEXT)
        session.prepare({'text':'What did I say?','context':[]})
        self.assertEqual(len(calls),1)
        self.assertEqual(session.cognitive_context,session.cognitive_history)
        self.assertIn('robin -> animal',session.cognitive_context[0]['text'])

    def test_native_failure_does_not_commit_or_generate_fallback(self):
        def fail(*args,**kwargs):raise TimeoutError('synthetic timeout')
        session=Session(None,None,reasoner=self.reasoner(fail))
        with self.assertRaises(NativePreparationError) as failed:
            session.prepare({'text':TEXT,'context':[]})
        self.assertIsInstance(failed.exception.__cause__,TimeoutError)
        self.assertEqual(session.history,[]);self.assertIsNone(session.pending)
        self.assertEqual(session.cognitive_history,[])

    def test_history_changes_revision_without_inventing_new_evidence(self):
        self.assertEqual(extract(TEXT,3)['revision'],3)
        self.assertEqual(extract(TEXT,3)['task_id'],'turn_3')

    def test_failed_model_turn_does_not_commit_staged_cognitive_memory(self):
        class Provider:
            def chat(self,messages):return 'Synthetic reply.'
        observations=iter([[{'id':'old','text':'Synthetic committed observation'}],
                           [{'id':'new','text':'Synthetic uncommitted observation'}],[]])
        provider=Provider();session=Session(provider,None,reasoner=lambda *_:next(observations))
        session.prepare({'text':'First','context':[]})
        messages=[session.user_message()];messages.append(session.infer(messages));session.commit(messages)
        committed=list(session.cognitive_history)
        session.prepare({'text':'Second','context':[]})
        def fail(_):raise TimeoutError('synthetic model failure')
        provider.chat=fail
        with self.assertRaises(TimeoutError):session.infer(session.history+[session.user_message()])
        self.assertEqual(session.cognitive_history,committed)
        session.prepare({'text':'Replacement','context':[]})
        self.assertEqual(session.cognitive_context,committed)
        self.assertEqual(len(session.history),2)

    def test_malformed_observation_is_not_staged(self):
        session=Session(None,None,reasoner=lambda *_:[{'text':'Missing identity'}])
        with self.assertRaises(ValueError):session.prepare({'text':'Hello','context':[]})
        self.assertIsNone(session.pending);self.assertEqual(session.cognitive_history,[])

    def test_expanded_hypothetical_labels_reach_synthetic_observation(self):
        text='Suppose that all song birds are small animals; all robins are song birds. What follows?'
        calls=[]
        def synthetic(request,**kwargs):
            calls.append(request)
            rows=[{'subject_index':a,'predicate_index':b,'frequency':float(f),'confidence':float(c)}
                  for (a,b),(f,c) in independent_expected(request).items()]
            return response_from_rows(request,rows),{'synthetic_test_only':True}
        reasoner=self.reasoner(synthetic)
        observation=reasoner(text,[])[0]
        self.assertIn('robins -> small animals',observation['text'])
        self.assertIn('two hypothetical premises',observation['text'])
        self.assertTrue(all(p['source'].startswith('hypothetical:') for p in calls[0]['premises']))
        self.assertEqual(reasoner.receipts[0]['term_labels']['small_animals'],'small animals')

    def test_binding_changes_native_request_and_embeds_full_identity(self):
        original=extract(TEXT,1)
        before=canonical(original)
        first={'session_id':'one','request_id':'request-a','revision':0}
        second={'session_id':'one','request_id':'request-b','revision':0}
        third={'session_id':'two','request_id':'request-a','revision':0}
        requests=[bind_request(original,b) for b in (first,second,third)]
        self.assertEqual(len({canonical(r) for r in requests}),3)
        self.assertEqual(canonical(original),before)
        for binding,request in zip((first,second,third),requests):
            digest=hashlib.sha256(canonical(binding)).hexdigest()
            self.assertEqual(request['task_id'],'req_'+digest[:28])
            self.assertEqual(request['revision'],original['revision'])
            for source,premise in zip(original['premises'],request['premises']):
                self.assertEqual(premise['source'],source['source']+';turn:'+digest)

    def test_fsynced_start_record_precedes_runner_and_post_record_is_parent_sidecar(self):
        binding={'session_id':'one','request_id':'r1','revision':0}
        observed=[]
        import cognition
        original_fsync=cognition.os.fsync
        def synthetic(request,**kwargs):
            native=kwargs['evidence_directory'];attempt=native.parent
            self.assertEqual(native.name,'native')
            self.assertFalse(native.exists())
            start=json.loads((attempt/'turn-start.json').read_text())
            self.assertEqual(start['phase'],'prepared')
            self.assertEqual(start['request'],request)
            self.assertEqual(start['turn_binding'],binding)
            self.assertEqual(start['native_request_sha256'],hashlib.sha256(canonical(request)).hexdigest())
            self.assertGreaterEqual(sync.call_count,2)  # File and directory before native execution.
            self.assertFalse((attempt/'turn-binding.json').exists())
            native.mkdir();observed.append(attempt)
            rows=[{'subject_index':a,'predicate_index':b,'frequency':float(f),'confidence':float(c)}
                  for (a,b),(f,c) in independent_expected(request).items()]
            return response_from_rows(request,rows),{'synthetic_test_only':True}
        reasoner=self.reasoner(synthetic)
        with patch('cognition.os.fsync',wraps=original_fsync) as sync:
            reasoner.reason_turn(TEXT,[],binding)
        attempt=observed[0]
        post=json.loads((attempt/'turn-binding.json').read_text())
        self.assertEqual(post['turn_binding'],binding)
        self.assertEqual(post['native_response_sha256'],hashlib.sha256(canonical(reasoner.receipts[0]['response'])).hexdigest())
        self.assertEqual(reasoner.receipts[0]['evidence_directory'],str(attempt))
        self.assertFalse((attempt/'native/turn-binding.json').exists())

    def test_timeout_preserves_preexecution_record_without_success_sidecar(self):
        binding={'session_id':'one','request_id':'cancelled','revision':0}
        directories=[]
        def timeout(request,**kwargs):
            attempt=kwargs['evidence_directory'].parent
            self.assertTrue((attempt/'turn-start.json').is_file())
            directories.append(attempt)
            raise TimeoutError('Synthetic native timeout; no native execution')
        reasoner=self.reasoner(timeout)
        with self.assertRaises(TimeoutError):reasoner.reason_turn(TEXT,[],binding)
        self.assertEqual(reasoner.receipts,[])
        start=json.loads((directories[0]/'turn-start.json').read_text())
        self.assertEqual(start['turn_binding'],binding)
        self.assertEqual(start['phase'],'prepared')
        self.assertFalse((directories[0]/'turn-binding.json').exists())

    def test_duplicate_fresh_observations_fail_before_staging(self):
        session=Session(None,None,reasoner=lambda *_:[{'id':'same','text':'First'}, {'id':'same','text':'Second'}])
        with self.assertRaises(NativePreparationError):session.prepare({'text':'Hello','context':[]})
        self.assertIsNone(session.pending)
        self.assertEqual(session.pending_cognition,[])
        self.assertEqual(session.cognitive_context,[])
        self.assertEqual(session.history,[])


if __name__=='__main__':unittest.main()
