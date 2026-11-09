"""Opt-in context policy contracts: explicit projection double, real SQLite."""
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


class ProjectionDouble:
    def __init__(self):
        self.profile = {'context_projection': 'extractive_v1'}
        self.model_context = None
        self.last_error = self.last_generation = None
        self.context_policy = 'complete'
        self.calls = []
        self.fail = False

    def chat(self, messages):
        self.calls.append((self.context_policy, copy.deepcopy(messages)))
        if self.fail:
            self.last_error = 'context_limit'
            raise ValueError('Synthetic projection cannot fit exact budget')
        if self.context_policy == 'extractive_v1':
            self.model_context = {'summary_policy': 'synthetic_extractive_test_only',
                                  'model_context_complete': False, 'omitted_count': 2,
                                  'token_count': 100}
        self.last_generation = {'input_tokens': 100, 'output_tokens': 3,
                                'finish_reason': 'eos'}
        return 'Synthetic answer.'


class ContextPolicyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            'ROKO_HISTORY_DB': str(Path(self.temp.name) / 'history.sqlite')})
        self.environment.start()
        self.previous = conversation.session
        api.current = api.immediate = api.completed = None
        self.provider = ProjectionDouble()
        self.reasoner_calls = []
        api.initialize(self.provider, lambda *a, **k: {'focus': []}, reasoner=self.reasoner)

    def tearDown(self):
        api.store.close()
        api.store = api.current = api.immediate = api.completed = None
        conversation.session = self.previous
        self.environment.stop()
        self.temp.cleanup()

    def reasoner(self, text, history):
        self.reasoner_calls.append(text)
        return [{'id': 'belief_' + text, 'text': 'Synthetic observation ' + text}]

    def prepare(self, request_id='first', revision=0, **fields):
        packet = {'api_version': 2, 'op': 'turn', 'session_id': 'policy',
                  'request_id': request_id, 'expected_revision': revision,
                  'text': request_id, 'context': []}
        packet.update(fields)
        return api.prepare_line(json.dumps(packet))

    def finish(self):
        session = conversation.session
        messages = session.history + [session.user_message()]
        answer = session.infer(messages)
        return json.loads(session.commit(messages + [answer]))

    def snapshot(self):
        return api.store.snapshot('policy', include_cognition=True)

    def test_opt_in_commits_full_history_and_cognition_with_explicit_loss_metadata(self):
        self.assertTrue(self.prepare())
        self.finish()
        before = self.snapshot()
        self.assertTrue(self.prepare('second', 1, context_policy='extractive_v1'))
        result = self.finish()
        self.assertEqual(self.provider.calls[-1][0], 'extractive_v1')
        self.assertEqual(result['model_context'], self.provider.model_context)
        self.assertFalse(result['model_context']['model_context_complete'])
        self.assertEqual(result['history_policy'], 'complete_no_omission')
        after = self.snapshot()
        self.assertEqual(after['history'][:2], before['history'])
        self.assertEqual(after['history'][-2:], [
            {'role': 'user', 'content': 'second'},
            {'role': 'assistant', 'content': 'Synthetic answer.'}])
        self.assertEqual(after['cognitive_history'], before['cognitive_history'] + [
            {'id': 'belief_second', 'text': 'Synthetic observation second'}])
        self.assertEqual(after['revision'], 2)

    def test_projection_failure_rolls_back_history_and_ledger(self):
        self.assertTrue(self.prepare())
        self.finish()
        before = self.snapshot()
        self.provider.fail = True
        self.assertTrue(self.prepare('failed', 1, context_policy='extractive_v1'))
        with patch.object(api.store, 'commit', wraps=api.store.commit) as commit:
            with self.assertRaisesRegex(ValueError, 'Synthetic projection'):
                self.finish()
            commit.assert_not_called()
        self.assertEqual(json.loads(api.abort())['code'], 'context_limit')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(conversation.session.pending_cognition, [])

    def test_replay_has_no_fresh_calls_and_changed_policy_conflicts(self):
        self.assertTrue(self.prepare(context_policy='extractive_v1'))
        saved = self.finish()
        calls = copy.deepcopy(self.provider.calls)
        reasons = list(self.reasoner_calls)
        self.assertFalse(self.prepare(context_policy='extractive_v1'))
        self.assertEqual(json.loads(api.immediate_json()), saved)
        self.assertFalse(self.prepare(context_policy='complete'))
        self.assertEqual(json.loads(api.immediate_json())['code'], 'request_conflict')
        self.assertEqual(self.provider.calls, calls)
        self.assertEqual(self.reasoner_calls, reasons)

    def test_old_default_payload_replays_with_omitted_or_explicit_complete_policy(self):
        claim = api.store.start('policy', 'first', 0,
                                {'text': 'first', 'context': [], 'max_output_tokens': 128})
        saved = api.store.commit(claim['token'], {'role': 'user', 'content': 'first'},
            {'role': 'assistant', 'content': 'Legacy saved answer'},
            {'api_version': 2, 'status': 'completed', 'text': 'Legacy saved answer'})
        for fields in ({}, {'context_policy': 'complete'}):
            self.assertFalse(self.prepare(**fields))
            self.assertEqual(json.loads(api.immediate_json()), saved)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.reasoner_calls, [])

    def test_default_resets_policy_and_does_not_leak_previous_projection_metadata(self):
        self.assertTrue(self.prepare(context_policy='extractive_v1'))
        self.assertIn('model_context', self.finish())
        self.assertTrue(self.prepare('second', 1))
        self.assertEqual(self.provider.context_policy, 'complete')
        self.assertIsNone(self.provider.model_context)
        self.assertNotIn('model_context', self.finish())
        self.assertEqual(self.provider.calls[-1][0], 'complete')

    def test_unknown_policy_rejected_before_claim(self):
        for policy in ('unknown', None, 1, [], {}):
            with self.subTest(policy=policy), patch.object(api.store, 'start') as start:
                self.assertFalse(self.prepare(context_policy=policy))
                self.assertEqual(json.loads(api.immediate_json())['code'], 'invalid_request')
                start.assert_not_called()
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.reasoner_calls, [])

    def test_missing_projection_capability_rejected_before_claim(self):
        self.provider.profile = {}
        before = self.database_state()
        self.assertFalse(self.prepare(context_policy='extractive_v1'))
        self.assertEqual(json.loads(api.immediate_json())['code'], 'unsupported_context_policy')
        self.assertEqual(self.database_state(), before)
        self.assertIsNone(api.current)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.reasoner_calls, [])

    def database_state(self):
        return (api.store.db.total_changes,
                [tuple(row) for row in api.store.db.execute('SELECT * FROM sessions ORDER BY id')],
                [tuple(row) for row in api.store.db.execute(
                    'SELECT * FROM requests ORDER BY session_id, request_id')])

    def test_saved_projection_replays_after_capability_removed_without_new_claim(self):
        self.assertTrue(self.prepare(context_policy='extractive_v1'))
        saved = self.finish()
        calls = copy.deepcopy(self.provider.calls)
        reasons = list(self.reasoner_calls)
        before = self.database_state()
        self.provider.profile = {}
        self.assertFalse(self.prepare(context_policy='extractive_v1'))
        self.assertEqual(json.loads(api.immediate_json()), saved)
        self.assertEqual(self.database_state(), before)
        self.assertFalse(self.prepare('second', 1, context_policy='extractive_v1'))
        self.assertEqual(json.loads(api.immediate_json())['code'], 'unsupported_context_policy')
        self.assertEqual(self.database_state(), before)
        self.assertEqual(self.provider.calls, calls)
        self.assertEqual(self.reasoner_calls, reasons)
        self.assertIsNone(api.current)


if __name__ == '__main__':
    unittest.main()
