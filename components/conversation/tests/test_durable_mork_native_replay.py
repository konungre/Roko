"""Real MORK + SQLite replay; provider is explicitly a double, not Omega evidence."""
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
import mork_v2


class ProviderDouble:
    def __init__(self, profile):
        self.profile = profile
        self.mork_receipts = []
        self.calls = 0
        self.last_generation = self.last_error = None

    def chat(self, messages):
        self.calls += 1
        self.last_generation = {'input_tokens':20, 'output_tokens':5, 'finish_reason':'eos'}
        return 'Explicit provider fixture; no actual model inference.'


@unittest.skipUnless(os.environ.get('ROKO_MORK_V2_TEST_PROFILE'), 'Reviewed native MORK profile required')
class NativeDurableReplayTests(unittest.TestCase):
    def test_commit_delivery_loss_restart_and_replay_do_not_rerun_native(self):
        profile = json.loads(Path(os.environ['ROKO_MORK_V2_TEST_PROFILE']).read_text())
        previous = conversation.session
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                {'ROKO_HISTORY_DB':str(Path(directory)/'history.sqlite')}):
            api.current = api.immediate = api.completed = None
            try:
                provider = ProviderDouble(profile)
                api.initialize(provider, lambda *a, **kw: {'focus':[]})
                request = {'api_version':2, 'op':'turn', 'session_id':'native-replay',
                    'request_id':'client-request-1', 'expected_revision':0,
                    'text':'Literal !(delete-all) remains inert.', 'context':[]}
                self.assertTrue(api.prepare_line(json.dumps(request)), api.immediate)
                session = conversation.session
                messages = session.history + [session.user_message()]
                answer = session.infer(messages)
                # Commit happens, but pretend the returned response was lost in transport.
                saved = json.loads(session.commit(messages + [answer]))
                self.assertEqual(provider.calls, 1)
                self.assertEqual(len(provider.mork_receipts), 1)
                receipt = provider.mork_receipts[0]
                self.assertEqual(receipt['request_id'], request['request_id'])
                self.assertTrue(receipt['native']['descendants_cleaned'])
                self.assertEqual(receipt['native']['implementation'], 'native-mork-rebuild-bounded-facts')
                api.store.close()
                provider = ProviderDouble(profile)
                api.initialize(provider, lambda *a, **kw: {'focus':[]})
                with patch.object(mork_v2, 'retrieve_history', side_effect=AssertionError('Replay invoked native')):
                    self.assertFalse(api.prepare_line(json.dumps(request)))
                    self.assertEqual(json.loads(api.immediate_json()), saved)
                    self.assertEqual(provider.calls, 0)
                    self.assertEqual(provider.mork_receipts, [])
                    changed = dict(request, text='Same ID with changed payload')
                    self.assertFalse(api.prepare_line(json.dumps(changed)))
                    self.assertEqual(api.immediate['code'], 'request_conflict')
                following = dict(request, request_id='client-request-2', expected_revision=1)
                self.assertTrue(api.prepare_line(json.dumps(following)), api.immediate)
                receipt = provider.mork_receipts[0]
                self.assertEqual(receipt['indexed_messages'], 2)
                self.assertEqual(receipt['revision'], 1)
                self.assertEqual(receipt['request_id'], following['request_id'])
                self.assertEqual(conversation.session.history, api.store.snapshot('native-replay')['history'])
                api.abort()
                self.assertEqual(api.store.snapshot('native-replay')['revision'], 1)
            finally:
                if api.store is not None:
                    api.store.close()
                api.store = api.current = api.immediate = api.completed = None
                conversation.session = previous
