import unittest,copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from reconnect_state import ReconnectState
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='keep me',context=[])
def snapshot(pending=None):return dict(api_version=2,status='snapshot',session_id='s',revision=0,pending=pending,history=[])
def controller():
    d=DesktopDraft('keep me');d.begin(REQ,confirmed=True);return d,ReconnectState(d)
class ReconnectTests(unittest.TestCase):
    def test_old_connection_snapshot_does_not_enable_replay(self):
        d,r=controller();old=r.request_snapshot(confirmed=True);r.service_lost()
        with self.assertRaises(ValueError):r.receive_snapshot(old['ticket'],snapshot())
        self.assertEqual(r.view()['phase'],'snapshot_required');self.assertEqual(d.view()['draft'],'keep me')
        with self.assertRaises(ValueError):d.propose('replay_original',confirmed=True)
    def test_latest_user_snapshot_wins_over_out_of_order_reply(self):
        d,r=controller();first=r.request_snapshot(confirmed=True);second=r.request_snapshot(confirmed=True)
        before=copy.deepcopy(r.view())
        with self.assertRaises(ValueError):r.receive_snapshot(first['ticket'],snapshot())
        self.assertEqual(r.view(),before)
        r.receive_snapshot(second['ticket'],snapshot('r'))
        self.assertEqual(r.view()['phase'],'pending_owner_review')
    def test_snapshot_does_not_claim_service_health_or_send(self):
        d,r=controller();r.service_lost();ticket=r.request_snapshot(confirmed=True)
        self.assertEqual(r.view()['phase'],'snapshot_requested')
        r.receive_snapshot(ticket['ticket'],snapshot())
        self.assertEqual(r.view()['phase'],'snapshot_review_required')
        self.assertEqual(r.view()['service_health'],'not_established');self.assertFalse(r.view()['automatic_requests'])
        self.assertEqual(d.propose('replay_original',confirmed=True),REQ)
    def test_duplicate_snapshot_completion_is_rejected(self):
        d,r=controller();t=r.request_snapshot(confirmed=True)['ticket'];r.receive_snapshot(t,snapshot())
        before=r.view()
        with self.assertRaises(ValueError):r.receive_snapshot(t,snapshot('r'))
        self.assertEqual(r.view(),before)
    def test_invalid_packet_retains_ticket_and_draft(self):
        d,r=controller();t=r.request_snapshot(confirmed=True)['ticket'];bad=snapshot();del bad['pending']
        before=r.view()
        with self.assertRaises(ValueError):r.receive_snapshot(t,bad)
        self.assertEqual(r.view(),before);r.receive_snapshot(t,snapshot())
    def test_outstanding_snapshot_and_later_error_block_old_decisions(self):
        d,r=controller();r.service_lost();t=r.request_snapshot(confirmed=True)['ticket'];r.receive_snapshot(t,snapshot())
        self.assertEqual(r.propose_action('replay_original',confirmed=True),REQ)
        t=r.request_snapshot(confirmed=True)['ticket']
        self.assertEqual(r.view()['draft_state']['active']['available_actions'],['snapshot'])
        with self.assertRaises(ValueError):r.propose_action('replay_original',confirmed=True)
        with self.assertRaises(ValueError):r.review_and_release(confirmed=True)
        r.receive_error(dict(api_version=2,status='error',code='busy',session_id='s',request_id='r'))
        with self.assertRaises(ValueError):r.receive_snapshot(t,snapshot())
        self.assertEqual(r.view()['phase'],'snapshot_required')

    def test_confirmation_and_ticket_types_fail_closed(self):
        d,r=controller()
        with self.assertRaises(ValueError):r.request_snapshot()
        t=r.request_snapshot(confirmed=True)['ticket']
        for bad in (None,[],[True,t[1]],['0',t[1]],[t[0],t[1]+1]):
            with self.assertRaises(ValueError):r.receive_snapshot(bad,snapshot())
        self.assertEqual(r.view()['phase'],'snapshot_requested')
if __name__=='__main__':unittest.main()
