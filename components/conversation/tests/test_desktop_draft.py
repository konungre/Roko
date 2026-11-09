import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='first draft',context=[])
def snap(pending=None, revision=0):
    return dict(api_version=2,status='snapshot',session_id='s',revision=revision,pending=pending,
                history=[dict(role='user',content='first draft'),dict(role='assistant',content='reply')]*revision)
class DraftTests(unittest.TestCase):
    def test_loss_edit_replay_retains_original_and_unsent_input(self):
        d=DesktopDraft('first draft');sent=d.begin(REQ,confirmed=True);sent['text']='mutated'
        d.edit('<b>next unsent draft</b>');d.transport_lost();d.receive_snapshot(snap(revision=1))
        self.assertEqual(d.propose('replay_original',confirmed=True),REQ)
        self.assertEqual(d.view()['draft'],'<b>next unsent draft</b>')
        self.assertEqual(len(d.view()['active']['transcript']),2)
        self.assertFalse(d.view()['automatic_requests']);self.assertFalse(d.view()['can_begin'])
    def test_duplicate_send_and_unconfirmed_actions_are_blocked(self):
        d=DesktopDraft('first draft')
        with self.assertRaises(ValueError):d.begin(REQ)
        d.begin(REQ,confirmed=True);d.transport_lost()
        with self.assertRaises(ValueError):d.begin(REQ,confirmed=True)
        with self.assertRaises(ValueError):d.propose('snapshot')
        with self.assertRaises(ValueError):d.review_and_release(confirmed=True)
        self.assertEqual(d.view()['draft'],'first draft')
    def test_live_pending_and_failed_recovery_preserve_draft(self):
        d=DesktopDraft('first draft');d.begin(REQ,confirmed=True);d.edit('new draft');d.transport_lost();d.receive_snapshot(snap(pending='r'))
        with self.assertRaises(ValueError):d.review_and_release(confirmed=True)
        with self.assertRaises(ValueError):d.propose('recover_pending',confirmed=True)
        self.assertEqual(d.propose('recover_pending',confirmed=True,owner_stopped=True)['op'],'recover')
        d.receive_error(dict(api_version=2,status='error',code='busy',session_id='s',request_id='r'))
        self.assertEqual(d.view()['draft'],'new draft');self.assertFalse(d.view()['can_begin'])
    def test_release_requires_user_review_and_never_clears_draft(self):
        d=DesktopDraft('first draft');d.begin(REQ,confirmed=True);d.transport_lost();d.receive_snapshot(snap())
        with self.assertRaises(ValueError):d.review_and_release()
        d.review_and_release(confirmed=True)
        self.assertEqual(d.view()['draft'],'first draft');self.assertTrue(d.view()['can_begin'])
        self.assertEqual(d.view()['outcome'],'not_established')
    def test_malformed_packet_preserves_draft_and_diagnostics(self):
        d=DesktopDraft('first draft');d.begin(REQ,confirmed=True);d.transport_lost();d.receive_snapshot(snap())
        before=copy.deepcopy(d.view());bad=snap();del bad['pending']
        with self.assertRaises(ValueError):d.receive_snapshot(bad)
        self.assertEqual(d.view(),before)
    def test_later_loss_invalidates_cached_snapshot_for_all_decisions(self):
        d=DesktopDraft('first draft');d.begin(REQ,confirmed=True);d.transport_lost();d.receive_snapshot(snap())
        self.assertEqual(d.propose('replay_original',confirmed=True),REQ)
        d.transport_lost()
        self.assertEqual(d.view()['active']['available_actions'],['snapshot'])
        with self.assertRaises(ValueError):d.propose('replay_original',confirmed=True)
        with self.assertRaises(ValueError):d.review_and_release(confirmed=True)
        self.assertEqual(d.propose('snapshot',confirmed=True)['op'],'snapshot')
        d.receive_snapshot(snap());self.assertEqual(d.propose('replay_original',confirmed=True),REQ)

    def test_capture_must_match_visible_draft(self):
        d=DesktopDraft('other')
        with self.assertRaises(ValueError):d.begin(REQ,confirmed=True)
        self.assertTrue(d.view()['can_begin']);self.assertEqual(d.view()['draft'],'other')
if __name__=='__main__':unittest.main()
