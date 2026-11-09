"""Resource-error recovery with explicit provider/reasoner doubles and real SQLite.

These exercise durable API error propagation, not native diagnostic classification
or actual model execution.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conversation
import durable_api as api


class ResourceProviderDouble:
    def __init__(self):
        self.last_error = None
        self.last_generation = None
        self.failure = None
        self.messages = []

    def chat(self, messages):
        self.messages.append(copy.deepcopy(messages))
        if self.failure:
            self.last_error = self.failure
            raise RuntimeError('Synthetic native failure: ' + self.failure)
        self.last_generation = {'input_tokens': 20, 'output_tokens': 3,
                                'finish_reason': 'eos'}
        return 'Synthetic recovery answer.'


class ResourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            'ROKO_HISTORY_DB': str(Path(self.temp.name) / 'history.sqlite')})
        self.environment.start()
        self.previous = conversation.session
        api.current = api.immediate = api.completed = None
        self.reasoner_calls = []
        self.start()

    def tearDown(self):
        api.store.close()
        api.store = api.current = api.immediate = api.completed = None
        conversation.session = self.previous
        self.environment.stop()
        self.temp.cleanup()

    def reasoner(self, text, history):
        self.reasoner_calls.append((text, copy.deepcopy(history)))
        return [{'id': 'observation_' + text, 'text': 'Synthetic belief ' + text}]

    def start(self):
        self.provider = ResourceProviderDouble()
        api.initialize(self.provider, lambda *args, **kwargs: {'focus': []},
                       reasoner=self.reasoner)

    def prepare(self, request_id, revision):
        return api.prepare_line(json.dumps({
            'api_version': 2, 'op': 'turn', 'session_id': 'recovery',
            'request_id': request_id, 'expected_revision': revision,
            'text': request_id, 'context': []}))

    def finish(self):
        session = conversation.session
        messages = session.history + [session.user_message()]
        answer = session.infer(messages)
        return json.loads(session.commit(messages + [answer]))

    def snapshot(self):
        return api.store.snapshot('recovery', include_cognition=True)

    def check_recovery(self, code, restart):
        for revision, request_id in enumerate(('first', 'second')):
            self.assertTrue(self.prepare(request_id, revision))
            self.finish()
        prior = self.snapshot()
        self.assertEqual(len(prior['history']), 4)
        self.assertEqual(len(prior['cognitive_history']), 2)
        self.provider.failure = code
        self.assertTrue(self.prepare('failed', 2))
        self.assertEqual(len(conversation.session.pending_cognition), 1)
        with patch.object(api.store, 'commit', wraps=api.store.commit) as commit:
            with self.assertRaisesRegex(RuntimeError, code):
                self.finish()
            commit.assert_not_called()
        error = json.loads(api.abort())
        self.assertEqual(error['code'], code)
        self.assertEqual(error['request_id'], 'failed')
        self.assertEqual(error['executed_actions'], 0)
        self.assertEqual(self.snapshot(), prior)
        self.assertIsNone(conversation.session.pending)
        self.assertEqual(conversation.session.pending_cognition, [])
        self.assertEqual(conversation.session.cognitive_context, prior['cognitive_history'])
        if restart:
            api.store.close()
            self.start()
        else:
            self.provider.failure = None
        model_calls = len(self.provider.messages)
        reasoner_calls = len(self.reasoner_calls)
        self.assertFalse(self.prepare('failed', 2))
        self.assertEqual(json.loads(api.immediate_json())['code'], 'failed')
        self.assertEqual(len(self.provider.messages), model_calls)
        self.assertEqual(len(self.reasoner_calls), reasoner_calls)
        self.assertTrue(self.prepare('successor', 2))
        self.assertIsNone(self.provider.last_error)
        self.assertEqual(conversation.session.history, prior['history'])
        self.assertEqual(conversation.session.cognitive_history, prior['cognitive_history'])
        self.assertEqual(self.reasoner_calls[-1][1], prior['history'])
        result = self.finish()
        self.assertEqual(result['revision'], 3)
        self.assertEqual(result['status'], 'completed')
        current = self.snapshot()
        self.assertEqual(current['history'][:4], prior['history'])
        self.assertEqual(len(current['history']), 6)
        self.assertEqual(current['history'][-2]['content'], 'successor')
        self.assertEqual(current['cognitive_history'], prior['cognitive_history'] + [
            {'id': 'observation_successor', 'text': 'Synthetic belief successor'}])
        prompt = self.provider.messages[-1]
        self.assertEqual(prompt[1:5], prior['history'])
        self.assertIn('Synthetic belief first', prompt[0]['content'])
        self.assertIn('Synthetic belief second', prompt[0]['content'])
        self.assertNotIn('Synthetic belief failed', prompt[0]['content'])

    def test_resource_limit_recovers_without_restart(self):
        self.check_recovery('resource_limit', False)

    def test_native_timeout_recovers_without_restart(self):
        self.check_recovery('native_timeout', False)

    def test_resource_limit_recovers_after_restart(self):
        self.check_recovery('resource_limit', True)

    def test_native_timeout_recovers_after_restart(self):
        self.check_recovery('native_timeout', True)


if __name__ == '__main__':
    unittest.main()
