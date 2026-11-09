"""Conversation integration contracts with explicitly synthetic runner results."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cognition import extract,NarsCognition
from conversation import Session
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
        with self.assertRaises(TimeoutError):session.prepare({'text':TEXT,'context':[]})
        self.assertEqual(session.history,[]);self.assertIsNone(session.pending)
        self.assertEqual(session.cognitive_history,[])

    def test_history_changes_revision_without_inventing_new_evidence(self):
        self.assertEqual(extract(TEXT,3)['revision'],3)
        self.assertEqual(extract(TEXT,3)['task_id'],'turn_3')


if __name__=='__main__':unittest.main()
