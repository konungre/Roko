import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sys,pathlib,unittest,copy
from cancellation_ux import CancellationUX
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='sent input',context=[],max_output_tokens=32)
def snap(pending=None,committed=False):return dict(api_version=2,status='snapshot',session_id='s',revision=1 if committed else 0,pending=pending,history=[dict(role='user',content='sent input'),dict(role='assistant',content='saved reply')] if committed else [])
def reply():return dict(api_version=2,status='completed',session_id='s',request_id='r',revision=1,text='saved reply',executed_actions=0)
def inspect(u,packet):
 q=u.inspect(confirmed=True);u.receive_snapshot(q['ticket'],packet);return q
class CancellationTests(unittest.TestCase):
 def begin(self):
  u=CancellationUX('sent input');u.begin(REQ,confirmed=True,owned_worker='local-worker');u.edit('new unsent draft');return u
 def test_cancel_is_proposal_not_recovery_or_duplicate_send(self):
  u=self.begin()
  with self.assertRaises(ValueError):u.request_cancel()
  p=u.request_cancel(confirmed=True);self.assertTrue(u.can_execute_cancel(p,current_binding=u.worker_binding()));self.assertEqual(u.view(500)['phase'],'stop_requested')
  with self.assertRaises(ValueError):u.request_cancel(confirmed=True)
  with self.assertRaises(ValueError):u.begin(dict(REQ,request_id='other'),confirmed=True)
  with self.assertRaises(ValueError):u.recover(confirmed=True)
  self.assertEqual(u.view()['draft'],'new unsent draft');self.assertIsNone(u.view()['transcript']);self.assertFalse(u.view()['transcript_available'])
 def test_cancel_without_owned_worker_is_not_offered(self):
  u=CancellationUX('sent input');u.begin(REQ,confirmed=True)
  self.assertFalse(u.view()['cancel_available'])
  with self.assertRaises(ValueError):u.request_cancel(confirmed=True)
 def test_dead_owner_requires_fresh_snapshot_and_explicit_recovery(self):
  u=self.begin();old=u.inspect(confirmed=True);p=u.request_cancel(confirmed=True);u.worker_stopped(p)
  with self.assertRaises(ValueError):u.receive_snapshot(old['ticket'],snap('r'))
  with self.assertRaises(ValueError):u.recover(confirmed=True)
  inspect(u,snap('r'))
  with self.assertRaises(ValueError):u.recover()
  proposal=u.recover(confirmed=True);self.assertEqual(proposal,dict(api_version=2,op='recover',session_id='s',request_id='r',expected_revision=0))
  with self.assertRaises(ValueError):u.recover(confirmed=True)
  u.receive_recovery_reply(dict(api_version=2,status='interrupted',session_id='s',request_id='r',revision=0),ticket=u.recovery_ticket())
  self.assertEqual(u.view()['request_outcome'],'interrupted_reported')
  with self.assertRaises(ValueError):u.receive_reply(reply())
  with self.assertRaises(ValueError):u.review_and_release(confirmed=True)
  inspect(u,snap());u.review_and_release(confirmed=True);self.assertEqual(u.view()['draft'],'new unsent draft')
 def test_committed_reply_wins_race_without_claiming_cancelled(self):
  u=self.begin();p=u.request_cancel(confirmed=True);u.receive_reply(reply());self.assertFalse(u.can_execute_cancel(p,current_binding=u.worker_binding()));self.assertEqual(u.view()['request_outcome'],'committed_reply_received')
  u.cancel_not_executed(p)
  with self.assertRaises(ValueError):u.review_and_release(confirmed=True)
  inspect(u,snap(committed=True));u.review_and_release(confirmed=True);self.assertEqual(u.view()['phase'],'idle');self.assertEqual(u.view()['draft'],'new unsent draft')
 def test_late_stop_keeps_committed_reply_and_never_recovers_it(self):
  u=self.begin();p=u.request_cancel(confirmed=True);u.receive_reply(reply());u.worker_stopped(p);inspect(u,snap(committed=True))
  self.assertEqual(u.view()['phase'],'reply_received_review_required')
  with self.assertRaises(ValueError):u.recover(confirmed=True)
  u.review_and_release(confirmed=True)
 def test_foreign_and_malformed_callbacks_do_not_replace_state(self):
  u=self.begin();p=u.request_cancel(confirmed=True);before=copy.deepcopy(u.view())
  with self.assertRaises(ValueError):u.worker_stopped(dict(p,worker_handle='other'))
  with self.assertRaises(ValueError):u.receive_reply(dict(reply(),request_id='other'))
  self.assertEqual(u.view(),before)
 def test_stale_cancel_after_explicit_retry_cannot_stop_new_turn(self):
  u=self.begin();first=u.request_cancel(confirmed=True);u.cancel_not_executed(first);second=u.request_cancel(confirmed=True)
  self.assertNotEqual(first,second);self.assertFalse(u.can_execute_cancel(first,current_binding=u.worker_binding()))
  with self.assertRaises(ValueError):u.worker_stopped(first)
  self.assertTrue(u.can_execute_cancel(second,current_binding=u.worker_binding()))
 def test_old_turn_snapshot_and_identity_cannot_be_reused(self):
  u=self.begin();u.transport_lost();old=inspect(u,snap());u.review_and_release(confirmed=True)
  with self.assertRaises(ValueError):u.begin(REQ,confirmed=True)
  new=dict(REQ,request_id='new',text='new unsent draft');u.begin(new,confirmed=True,owned_worker='local-worker')
  with self.assertRaises(ValueError):u.receive_snapshot(old['ticket'],snap())
 def test_reply_text_is_defensive_and_unknown_actions_are_not_exposed(self):
  u=self.begin();p=reply();p['actions']=['execute something'];u.receive_reply(p);p['text']='changed'
  v=u.view();self.assertNotIn('actions',v['received_reply']);self.assertEqual(v['received_reply']['text'],'saved reply');v['received_reply']['text']='mutated';self.assertEqual(u.view()['received_reply']['text'],'saved reply')
 def test_busy_recovery_requires_new_inspection_not_automatic_retry(self):
  u=self.begin();p=u.request_cancel(confirmed=True);u.worker_stopped(p);inspect(u,snap('r'));u.recover(confirmed=True)
  u.receive_recovery_reply(dict(api_version=2,status='error',code='busy',session_id='s',request_id='r'),ticket=u.recovery_ticket())
  self.assertEqual(u.view()['last_recovery_error'],'busy');self.assertEqual(u.view()['draft'],'new unsent draft')
  with self.assertRaises(ValueError):u.recover(confirmed=True)
  with self.assertRaises(ValueError):u.review_and_release(confirmed=True)
  inspect(u,snap('r'))
  with self.assertRaises(ValueError):u.recover()
  self.assertEqual(u.recover(confirmed=True)['op'],'recover')
 def test_malformed_identity_does_not_capture_or_send(self):
  u=CancellationUX('sent input')
  with self.assertRaises(ValueError):u.begin(dict(REQ,session_id=[]),confirmed=True)
  self.assertEqual(u.view()['phase'],'idle')

 def test_replay_clicks_are_single_flight_and_identity_is_immutable(self):
  u=self.begin();u.transport_lost();inspect(u,snap(committed=True));proposal=u.replay(confirmed=True)
  self.assertEqual(proposal,REQ);proposal['expected_revision']=100
  with self.assertRaises(ValueError):u.replay(confirmed=True)
  with self.assertRaises(ValueError):u.review_and_release(confirmed=True)
  u.receive_error(dict(api_version=2,status='error',code='pending',session_id='s',request_id='r'))
  self.assertEqual(u.view()['last_turn_error'],'pending');self.assertFalse(u.view()['replay_pending'])
  with self.assertRaises(ValueError):u.replay(confirmed=True)
  u.transport_lost();inspect(u,snap(committed=True));self.assertEqual(u.replay(confirmed=True),REQ)
  u.receive_reply(reply());self.assertFalse(u.view()['replay_pending']);self.assertEqual(u.view()['draft'],'new unsent draft')

 def test_shared_worker_binding_must_still_match_at_execution(self):
  u=self.begin();p=u.request_cancel(confirmed=True);binding=u.worker_binding();binding['request_id']='another-request'
  self.assertFalse(u.can_execute_cancel(p,current_binding=binding));self.assertFalse(u.can_execute_cancel(p,current_binding=None))
  self.assertTrue(u.can_execute_cancel(p,current_binding=u.worker_binding()))

 def test_current_reply_panel_rejects_authority_before_cancel_is_suppressed(self):
  u=self.begin();p=u.request_cancel(confirmed=True);before=u.view()
  with self.assertRaises(ValueError):u.receive_reply(dict(reply(),executed_actions=1))
  self.assertEqual(u.view(),before);self.assertTrue(u.can_execute_cancel(p,current_binding=u.worker_binding()))

 def test_lost_recovery_pending_claim_can_be_explicitly_retried(self):
  u=self.begin();stop=u.request_cancel(confirmed=True);u.worker_stopped(stop);inspect(u,snap('r'));u.recover(confirmed=True);old=u.recovery_ticket();stale=u.inspect(confirmed=True);u.transport_lost()
  with self.assertRaises(ValueError):u.reconcile_recovery(confirmed=True)
  with self.assertRaises(ValueError):u.receive_snapshot(stale['ticket'],snap('r'))
  inspect(u,snap('r'));latest=u.inspect(confirmed=True)
  with self.assertRaises(ValueError):u.reconcile_recovery(confirmed=True)
  u.receive_snapshot(latest['ticket'],snap('r'))
  with self.assertRaises(ValueError):u.reconcile_recovery()
  self.assertEqual(u.reconcile_recovery(confirmed=True)['resolution'],'pending_claim')
  with self.assertRaises(ValueError):u.recover()
  u.recover(confirmed=True);current=u.recovery_ticket();self.assertNotEqual(current,old)
  packet=dict(api_version=2,status='interrupted',session_id='s',request_id='r',revision=0)
  with self.assertRaises(ValueError):u.receive_recovery_reply(packet,ticket=old)
  u.receive_recovery_reply(packet,ticket=current);inspect(u,snap());u.review_and_release(confirmed=True)
  self.assertEqual(u.view()['draft'],'new unsent draft')
 def test_lost_recovery_no_pending_can_be_reviewed_without_false_interruption_claim(self):
  u=self.begin();stop=u.request_cancel(confirmed=True);u.worker_stopped(stop);inspect(u,snap('r'));u.recover(confirmed=True);old=u.recovery_ticket();u.transport_lost();inspect(u,snap())
  with self.assertRaises(ValueError):u.review_and_release(confirmed=True)
  self.assertEqual(u.reconcile_recovery(confirmed=True)['resolution'],'no_pending_claim')
  self.assertNotEqual(u.view()['request_outcome'],'interrupted_reported')
  with self.assertRaises(ValueError):u.receive_recovery_reply(dict(api_version=2,status='interrupted',session_id='s',request_id='r',revision=0),ticket=old)
  u.review_and_release(confirmed=True);self.assertEqual(u.view()['draft'],'new unsent draft')
 def test_stop_during_replay_fences_snapshot_and_unblocks_explicit_recovery(self):
  u=self.begin();u.transport_lost();inspect(u,snap());u.replay(confirmed=True);stale=u.inspect(confirmed=True);stop=u.request_cancel(confirmed=True);u.worker_stopped(stop)
  self.assertFalse(u.view()['replay_pending'])
  with self.assertRaises(ValueError):u.receive_snapshot(stale['ticket'],snap('r'))
  inspect(u,snap('r'));self.assertEqual(u.recover(confirmed=True)['op'],'recover')

if __name__=='__main__':unittest.main()
