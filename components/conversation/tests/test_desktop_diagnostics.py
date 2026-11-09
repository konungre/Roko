"""Desktop proposals preserve identity/history and require explicit user actions."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_diagnostics import DesktopDiagnostics
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='Hi',context=[],context_policy='extractive_v1')
def snapshot(revision=0,pending=None):return dict(api_version=2,status='snapshot',session_id='s',revision=revision,pending=pending,history=[{'role':'user','content':'<script>literal</script>'},{'role':'assistant','content':'Literal reply'}]*revision)
class DesktopTests(unittest.TestCase):
    def test_no_request_without_user_confirmation(self):
        d=DesktopDiagnostics(REQ);d.transport_lost()
        with self.assertRaises(ValueError):d.request_for_user_action('snapshot')
        self.assertFalse(d.view()['automatic_requests'])
    def test_exact_replay_preserves_old_revision_after_new_snapshot(self):
        original=copy.deepcopy(REQ);d=DesktopDiagnostics(original);d.transport_lost()
        original['expected_revision']=100;original['context'].append({'bad':'mutation'})
        with self.assertRaises(ValueError):d.request_for_user_action('replay_original',confirmed=True)
        d.receive_snapshot(snapshot(1))
        self.assertEqual(d.request_for_user_action('replay_original',confirmed=True),REQ)
        self.assertEqual(d.view()['snapshot_revision'],1)
    def test_history_plain_text_complete_and_defensive_copy(self):
        d=DesktopDiagnostics(REQ);s=snapshot(2);d.receive_snapshot(s)
        view=d.view();self.assertEqual(view['transcript'],s['history']);self.assertTrue(view['render_as_plain_text'])
        view['transcript'].clear();s['history'].clear();self.assertEqual(len(d.view()['transcript']),4)
    def test_pending_cannot_be_replayed_or_recovered_automatically(self):
        d=DesktopDiagnostics(REQ);d.receive_error(dict(api_version=2,status='error',code='pending'));d.receive_snapshot(snapshot(pending='r'))
        with self.assertRaises(ValueError):d.request_for_user_action('recover_pending',confirmed=True)
        with self.assertRaises(ValueError):d.request_for_user_action('replay_original',confirmed=True)
        proposal=d.request_for_user_action('recover_pending',confirmed=True,owner_stopped=True)
        self.assertEqual(proposal,dict(api_version=2,op='recover',session_id='s',request_id='r',expected_revision=0))
        self.assertEqual(d.view()['pending'],'r')
    def test_transport_loss_pending_snapshot_allows_only_confirmed_recovery(self):
        d=DesktopDiagnostics(REQ);d.transport_lost();d.receive_snapshot(snapshot(pending='r'))
        self.assertIn('recover_pending',d.view()['available_actions'])
        self.assertNotIn('replay_original',d.view()['available_actions'])
        self.assertTrue(d.view()['recovery_requires_verified_dead_owner'])
        with self.assertRaises(ValueError):d.request_for_user_action('recover_pending',confirmed=True)
        packet=d.request_for_user_action('recover_pending',confirmed=True,owner_stopped=True)
        self.assertEqual(packet['request_id'],'r');self.assertEqual(packet['expected_revision'],0)
        self.assertEqual(d.view()['pending'],'r')

    def test_foreign_pending_claim_is_not_recoverable(self):
        d=DesktopDiagnostics(REQ);d.receive_error(dict(api_version=2,status='error',code='busy'));d.receive_snapshot(snapshot(pending='other'))
        with self.assertRaises(ValueError):d.request_for_user_action('recover_pending',confirmed=True,owner_stopped=True)
    def test_invalid_snapshot_does_not_replace_existing_history(self):
        d=DesktopDiagnostics(REQ);d.receive_snapshot(snapshot(1));bad=snapshot(2);bad['history'].pop()
        with self.assertRaises(ValueError):d.receive_snapshot(bad)
        self.assertEqual(d.view()['snapshot_revision'],1)
    def test_stale_or_rewritten_snapshot_cannot_drop_transcript(self):
        d=DesktopDiagnostics(REQ);d.receive_snapshot(snapshot(2))
        for bad in (snapshot(1),snapshot(3)):
            if bad['revision']==3:bad['history'][0]['content']='rewritten'
            with self.assertRaises(ValueError):d.receive_snapshot(bad)
        self.assertEqual(len(d.view()['transcript']),4)

    def test_unrelated_errors_cannot_change_current_guidance(self):
        d=DesktopDiagnostics(REQ);d.transport_lost();before=d.view()
        for packet in (None,dict(api_version=2,status='error',code='pending',request_id='other')):
            with self.assertRaises(ValueError):d.receive_error(packet)
        self.assertEqual(d.view(),before)

    def test_resource_failure_does_not_offer_replay(self):
        d=DesktopDiagnostics(REQ);d.receive_error(dict(api_version=2,status='error',code='resource_limit'));d.receive_snapshot(snapshot())
        with self.assertRaises(ValueError):d.request_for_user_action('replay_original',confirmed=True)
    def test_remote_actions_are_not_executed_or_displayed(self):
        d=DesktopDiagnostics(REQ);d.receive_error(dict(api_version=2,status='error',code='unknown',actions=['run arbitrary program']))
        self.assertNotIn('arbitrary',str(d.view()))
        d.receive_snapshot(snapshot())
        with self.assertRaises(ValueError):d.request_for_user_action('run arbitrary program',confirmed=True)
if __name__=='__main__':unittest.main()
