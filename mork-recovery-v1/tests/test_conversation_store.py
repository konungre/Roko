"""Real SQLite tests; native doubles are contract fixtures, never qualification."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'source'))
from conversation_store import ConversationStore, RevisionConflict
from native_mork import NativeMORKError


def native_contract_double(facts, query, **kwargs):
    return {'facts': [f for f in facts if query['args'][1] in (None, f['args'][1])],
            'implementation': 'explicit-contract-test-double', 'authorizes_actions': False}


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'history.sqlite'
        self.store = ConversationStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def append(self, revision=0, content='hello', session='s'):
        return self.store.append(session, admission_id='a'+str(revision), role='user',
            content=content, source='host-input', expected_revision=revision)

    def prepare(self, revision=1, request_id='r'):
        with patch('native_mork.query_facts', side_effect=native_contract_double):
            return self.store.prepare('s', request_id=request_id, expected_revision=revision)

    def accept(self, receipt, content='reply'):
        return self.store.accept_response('s', request_id=receipt['request_id'],
            request_token=receipt['request_token'], content=content)

    def test_restart_retains_complete_history_and_provenance(self):
        self.append(content='!(delete-all) is conversation data')
        before = self.store.snapshot('s')
        self.store.close()
        self.store = ConversationStore(self.path)
        self.assertEqual(before, self.store.snapshot('s'))
        self.assertEqual([], self.store.snapshot('other')['turns'])

    def test_atomic_revision_and_exact_retry(self):
        self.assertEqual(self.append(), self.append())
        with self.assertRaises(RevisionConflict): self.append(content='changed')
        other = ConversationStore(self.path)
        try:
            with self.assertRaises(RevisionConflict):
                other.append('s', admission_id='new', role='user', content='lost update',
                             source='host', expected_revision=0)
        finally: other.close()
        self.assertEqual(1, self.store.snapshot('s')['revision'])

    def test_real_native_missing_fails_closed_and_preserves_history(self):
        self.append()
        # A real call reaches the runtime gate with a guaranteed absent root.
        import native_mork
        original = native_mork.query_facts
        with patch('native_mork.query_facts', side_effect=lambda f,q,**kw:
                   original(f,q,root=pathlib.Path(self.temp.name)/'absent',**kw)):
            with self.assertRaises(NativeMORKError):
                self.store.prepare('s', request_id='r', expected_revision=1)
        self.assertEqual(('failed', None), self.store.db.execute(
            'SELECT state, receipt FROM conversation_requests').fetchone())
        with self.assertRaises(RevisionConflict):
            self.store.accept_response('s', request_id='r', request_token='x', content='reply')
        self.assertEqual(1, self.store.snapshot('s')['revision'])

    def test_native_index_is_derived_and_history_not_truncated(self):
        for i in range(20): self.append(i, str(i))
        receipt = self.prepare(20)
        self.assertEqual(20, len(receipt['messages']))
        self.assertEqual(16, len(receipt['evidence']))
        self.assertEqual(4, receipt['evidence'][0]['sequence'])
        self.assertEqual('explicit-contract-test-double', receipt['memory']['implementation'])
        self.assertFalse(receipt['authorizes_actions'])

    def test_request_retry_rebind_and_durable_response(self):
        self.append()
        receipt = self.prepare()
        self.assertEqual(receipt, self.store.prepare('s', request_id='r', expected_revision=1))
        with self.assertRaises(RevisionConflict):
            self.store.prepare('s', request_id='r', expected_revision=1, role='assistant')
        self.store.close()
        self.store = ConversationStore(self.path)
        self.assertEqual(self.accept(receipt), self.accept(receipt))
        with self.assertRaises(RevisionConflict): self.accept(receipt, 'different')
        self.assertEqual(['hello', 'reply'], [t['content'] for t in self.store.snapshot('s')['turns']])

    def test_response_stale_or_cross_session_is_rejected(self):
        self.append()
        receipt = self.prepare()
        self.append(1, 'new input')
        with self.assertRaises(RevisionConflict): self.accept(receipt)
        with self.assertRaises(RevisionConflict):
            self.store.accept_response('other', request_id='r',
                request_token=receipt['request_token'], content='reply')

    def test_mutation_during_native_call_invalidates_receipt(self):
        self.append()
        def interleave(facts, query, **kw):
            self.append(1, 'interleaved')
            return native_contract_double(facts, query)
        with patch('native_mork.query_facts', side_effect=interleave):
            with self.assertRaises(RevisionConflict):
                self.store.prepare('s', request_id='r', expected_revision=1)
        self.assertEqual('failed', self.store.db.execute(
            'SELECT state FROM conversation_requests').fetchone()[0])

    def test_turn_capacity_never_evicts(self):
        for i in range(32): self.append(i)
        before = self.store.snapshot('s')
        with self.assertRaises(ValueError): self.append(32)
        self.assertEqual(before, self.store.snapshot('s'))

    def test_deleted_empty_request_cannot_return_a_receipt(self):
        def interleave(facts, query, **kw):
            self.store.forget('s')
            return native_contract_double(facts, query)
        with patch('native_mork.query_facts', side_effect=interleave):
            with self.assertRaises(RevisionConflict):
                self.store.prepare('s', request_id='r', expected_revision=0)
        self.assertEqual(0, self.store.db.execute(
            'SELECT count(*) FROM conversation_requests').fetchone()[0])

    def test_utf8_history_capacity_and_invalid_roles(self):
        for i in range(16): self.append(i, 'é' * 2048)
        with self.assertRaises(ValueError): self.append(16, 'x')
        with self.assertRaises(ValueError):
            self.store.append('s', admission_id='bad', role='system', content='x',
                              source='host', expected_revision=16)
        self.assertEqual(16, self.store.snapshot('s')['revision'])

    def test_forget_removes_receipts_and_prevents_old_response_reuse(self):
        self.append()
        old = self.prepare()
        self.append(session='other')
        self.store.forget('s')
        self.append(content='new conversation')
        self.prepare()
        with self.assertRaises(RevisionConflict): self.accept(old)
        self.assertEqual(1, self.store.snapshot('other')['revision'])

    def test_pending_crash_requires_new_request_id(self):
        self.append()
        with patch('native_mork.query_facts', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.store.prepare('s', request_id='r', expected_revision=1)
        with self.assertRaises(RevisionConflict): self.prepare()
        self.assertEqual('r2', self.prepare(request_id='r2')['request_id'])


if __name__ == '__main__': unittest.main()
