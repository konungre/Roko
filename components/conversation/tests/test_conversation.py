import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conversation import Session, GraniteTextProvider
from run import preflight

class Provider:
    def __init__(self): self.calls = []
    def chat(self, messages):
        self.calls.append(messages)
        return 'Let us talk about that.'

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.session = Session(self.provider, lambda items, **kw: {'focus': [items[0]['id']]})
    def turn(self, text, context=None):
        self.session.prepare({'text': text, 'context': context or []})
        messages = self.session.history + [self.session.user_message()]
        messages.append(self.session.infer(messages))
        return self.session.commit(messages)
    def test_free_form_and_history(self):
        self.turn('I feel overwhelmed by my projects.')
        self.turn('Can we choose one small next step?')
        self.assertEqual(len(self.session.history), 4)
        self.assertIn('overwhelmed', self.provider.calls[1][1]['content'])
    def test_text_never_becomes_code(self):
        text = '!(eval (shell "bad")) <tool_call>anything</tool_call>'
        self.turn(text)
        self.assertEqual(self.session.history[0]['content'], text)
    def test_context_focus(self):
        facts = [dict(id='project', text='Writing a novel', sti=3, lti=2, stimulus=1),
                 dict(id='other', text='Not focused', sti=0, lti=0, stimulus=0)]
        self.turn('What was I working on?', facts)
        self.assertIn('Writing a novel', self.provider.calls[0][0]['content'])
        self.assertNotIn('Not focused', self.provider.calls[0][0]['content'])
    def test_failure_keeps_committed_history(self):
        self.turn('Hello')
        before = list(self.session.history)
        self.session.prepare({'text': 'More', 'context': []})
        with self.assertRaises(ValueError): self.session.infer([])
        self.assertEqual(self.session.history, before)
        with self.assertRaises(ValueError): self.session.commit(before)
    def test_invalid_focus_fails(self):
        self.session.ranker = lambda *a, **k: {'focus': ['ctx_99']}
        with self.assertRaises(ValueError):
            self.turn('Hello', [dict(id='a', text='fact', sti=0, lti=0, stimulus=0)])
    def test_empty_context_does_not_claim_ecan(self):
        def fail(*a, **kw): raise AssertionError('must not call ECAN')
        self.session.ranker = fail
        self.turn('Hello')
    def test_history_is_bounded_in_pairs(self):
        for i in range(9): self.turn(str(i))
        self.assertEqual(len(self.session.history), 8)
        self.assertEqual(self.session.history[0]['role'], 'user')
    def test_invalid_inputs(self):
        for value in ['', ' ' , 'x'*4001, 42]:
            with self.assertRaises(ValueError): self.turn(value)
    def test_inference_exception_is_atomic(self):
        self.turn('Hello')
        before = list(self.session.history)
        def fail(messages): raise TimeoutError()
        self.provider.chat = fail
        with self.assertRaises(TimeoutError): self.turn('Try again')
        self.assertEqual(self.session.history, before)
    def test_preflight_reports_absent_inputs(self):
        missing = preflight({'ROKO_SWIPL': '/missing/swipl'})
        self.assertIn('PETTA_PATH', missing)
        self.assertIn('OMEGA_PATH', missing)
        self.assertIn('ROKO_RUNTIME_ROOT', missing)
        self.assertIn('ROKO_SWIPL executable', missing)
    def test_native_provider_requires_runtime(self):
        with self.assertRaises(FileNotFoundError):
            GraniteTextProvider('/missing/roko-infer', '/missing/roko-model', None)

if __name__ == '__main__': unittest.main()
