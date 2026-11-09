"""Guidance stays explicit and preserves ambiguous delivery/recovery semantics."""
import json,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from client_diagnostics import describe_error,describe_transport_failure
from durable_store import Store,StoreError

def error(code,**extra):return {'api_version':2,'status':'error','code':code,**extra}
class DiagnosticsTests(unittest.TestCase):
    def test_pending_never_assumes_dead_owner(self):
        for code in ('pending','busy'):
            r=describe_error(error(code));self.assertTrue(r['requires_verified_dead_owner'])
            self.assertFalse(r['automatic_retry']);self.assertEqual(r['next_operation'],'snapshot')
            self.assertIn('server verifies',r['message'])
    def test_delivery_loss_keeps_commit_outcome_unknown(self):
        r=describe_transport_failure();self.assertEqual(r['outcome'],'unknown')
        self.assertEqual(r['retry_mode'],'exact_original_request_after_snapshot')
        self.assertFalse(r['automatic_retry'])
    def test_resource_and_terminal_failures_require_new_id(self):
        for code in ('native_timeout','resource_limit','native_cancelled','failed','interrupted','context_projection_limit'):
            r=describe_error(error(code));self.assertEqual(r['retry_mode'],'new_id_after_review')
            self.assertTrue(r['requires_user_decision']);self.assertFalse(r['automatic_retry'])
    def test_full_session_guidance_requires_explicit_new_session(self):
        r=describe_error(error('history_limit'))
        self.assertEqual(r['retry_mode'],'new_session_after_snapshot')
        self.assertFalse(r['automatic_retry'])
        self.assertIn('complete history remains available',r['message'])

    def test_unknown_or_malicious_fields_never_become_displayed_guidance(self):
        attack='<script>doSomething()</script>; $(private-data)'
        for code in (attack,'future_unknown',[],None,True,'x'*65):
            r=describe_error(error(code,details=attack,session_id=attack))
            self.assertEqual(r['code'],'unknown_error');self.assertNotIn(attack,json.dumps(r))
            self.assertFalse(r['automatic_retry'])
    def test_success_and_wrong_protocol_are_not_errors(self):
        for packet in ({'api_version':2,'status':'completed'},error('failed',api_version=True),error('failed',api_version=1)):
            with self.assertRaises(ValueError):describe_error(packet)
    def test_replay_keeps_original_revision_after_snapshot_advances(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(str(Path(temp)/'history.sqlite'))
            try:
                payload={'text':'Hi'}
                claim=store.start('s','r',0,payload)
                saved=store.commit(claim['token'],{'role':'user','content':'Hi'},
                    {'role':'assistant','content':'Hello'},{'text':'Hello'})
                self.assertEqual(store.snapshot('s')['revision'],1)
                with self.assertRaises(StoreError) as raised:store.start('s','r',1,payload)
                self.assertEqual(raised.exception.code,'request_conflict')
                self.assertEqual(store.start('s','r',0,payload)['response'],saved)
                self.assertIn('expected_revision',describe_transport_failure()['message'])
            finally:store.close()

    def test_conflict_does_not_suggest_replay_of_changed_payload(self):
        r=describe_error(error('request_conflict'));self.assertIn('exact original request',r['message']);self.assertIn('expected_revision',r['message'])
        self.assertEqual(r['retry_mode'],'original_request_or_new_id_after_review')
if __name__=='__main__':unittest.main()
