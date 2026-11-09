"""Real SQLite atomicity; the marked native fixture is not engine evidence."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'components/conversation'), str(ROOT/'mork-recovery-v1/source')]
from conversation_store import ConversationStore, RevisionConflict
from durable_session import DurableSession, open_session


class NativeContractDouble:
    def query_facts(self, facts, query, **kw):
        return {'implementation':'explicit-test-double','facts':facts,
                'authorizes_actions':False}


class DurableConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name)/'history.sqlite'
        self.store = ConversationStore(self.path,native_backend=NativeContractDouble())
        self.session = DurableSession(object(),None,self.store,'s',None)

    def tearDown(self):
        self.session.close()
        self.temp.cleanup()

    def prepare(self):
        self.session.prepare({'text':'lighthouse','context':[]})
        return self.session.prepared

    def test_prepare_does_not_commit_and_restart_abandons_staged_text(self):
        receipt = self.prepare()
        self.assertEqual([],self.store.snapshot('s')['turns'])
        self.session.close()
        self.store = ConversationStore(self.path,native_backend=NativeContractDouble())
        self.session = DurableSession(object(),None,self.store,'s',None)
        self.assertEqual([],self.session.history)
        self.assertEqual(('failed',None),self.store.db.execute(
            'SELECT state,receipt FROM conversation_requests').fetchone())
        with self.assertRaises(RevisionConflict):
            self.store.accept_exchange('s',request_id=receipt['request_id'],
                request_token=receipt['request_token'],content='late answer')

    def test_complete_exchange_is_atomic_and_restored(self):
        receipt = self.prepare()
        self.session.reply = 'An opening sentence.'
        messages = [self.session.user_message(),{'role':'assistant','content':self.session.reply}]
        result = json.loads(self.session.commit(messages))
        self.assertEqual({'text','context_ids','executed_actions'},set(result))
        self.assertEqual(0,result['executed_actions'])
        self.assertEqual(2,self.store.snapshot('s')['revision'])
        self.assertEqual(2,self.store.accept_exchange('s',request_id=receipt['request_id'],
            request_token=receipt['request_token'],content='An opening sentence.'))
        self.session.close()
        self.store = ConversationStore(self.path,native_backend=NativeContractDouble())
        self.session = DurableSession(object(),None,self.store,'s',None)
        self.assertEqual(messages,self.session.history)
        self.session.prepare({'text':'What setting?','context':[]})
        self.assertEqual(2,len(self.session.prepared['evidence']))

    def test_failed_omega_identity_does_not_partially_commit(self):
        self.prepare()
        self.session.reply = 'reply'
        with self.assertRaises(ValueError): self.session.commit([])
        self.assertEqual(0,self.store.snapshot('s')['revision'])

    def test_exchange_overflow_rolls_back_both_rows(self):
        for i in range(15):
            self.store.append('overflow',admission_id=str(i),role='user',content='x'*4096,
                              source='fixture',expected_revision=i)
        receipt = self.store.prepare_exchange('overflow',request_id='q',expected_revision=15,
                                              content='x',source='fixture')
        with self.assertRaises(ValueError):
            self.store.accept_exchange('overflow',request_id='q',
                request_token=receipt['request_token'],content='x'*4096)
        self.assertEqual(15,self.store.snapshot('overflow')['revision'])

    def test_single_response_api_cannot_commit_exchange(self):
        receipt = self.prepare()
        with self.assertRaises(RevisionConflict):
            self.store.accept_response('s',request_id=receipt['request_id'],
                request_token=receipt['request_token'],content='wrong route')
        self.assertEqual(0,self.store.snapshot('s')['revision'])

    def test_exclusive_host_lease_prevents_concurrent_session(self):
        profile = {'python':sys.executable,'durable_memory':{
            'manifest':'unused-contract-fixture','manifest_sha256':'fixture',
            'database':str(pathlib.Path(self.temp.name)/'leased.sqlite'),'session':'leased'}}
        with patch('mork_host.ExternalMORKBackend',return_value=NativeContractDouble()):
            owner = open_session(object(),None,profile)
            try:
                with self.assertRaises(BlockingIOError):open_session(object(),None,profile)
            finally:owner.close()
            replacement = open_session(object(),None,profile)
            replacement.close()


if __name__ == '__main__':unittest.main()
