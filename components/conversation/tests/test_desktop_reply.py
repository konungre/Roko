"""Candidate desktop contract only; no actual GUI or transport is exercised."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from desktop_reply import DesktopReplyPanel
from test_package_reply_view import reply

REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='original draft',context=[])


def snapshot(answer,revision=1):
    return dict(api_version=2,status='snapshot',session_id='s',revision=revision,pending=None,
        history=[] if revision==0 else [dict(role='user',content=REQ['text']),dict(role='assistant',content=answer)])


class DesktopReplyTests(unittest.TestCase):
    def begin(self):
        draft=DesktopDraft(REQ['text']);draft.begin(REQ,confirmed=True);return draft
    def test_matching_reply_presents_notice_without_establishing_outcome_or_snapshot(self):
        draft=self.begin();draft.receive_reply(reply());view=draft.view();panel=view['active']['reply']
        self.assertIn('Live host, running system, activation and health: not established',panel['display_text'])
        self.assertIn('Generated answer (package claims are advisory):',panel['display_text'])
        self.assertEqual(panel['history_relation'],'snapshot_unavailable')
        self.assertFalse(panel['source_check_refreshed']);self.assertFalse(panel['mutation_authority'])
        self.assertTrue(view['needs_snapshot']);self.assertFalse(view['can_begin'])
        self.assertEqual(view['outcome'],'not_established');self.assertEqual(view['active']['transcript'],[])
        with self.assertRaises(ValueError):draft.review_and_release(confirmed=True)
    def test_received_packet_and_view_mutation_cannot_rewrite_accepted_reply(self):
        draft=self.begin();packet=reply();draft.receive_reply(packet);before=draft.view()
        packet['text']='changed';packet['package_state']['source']['machine']='other'
        returned=draft.view();returned['active']['reply']['display_text']='changed view'
        self.assertEqual(draft.view(),before)
    def test_new_unsent_typing_remains_separate_from_reply_and_history(self):
        draft=self.begin();draft.edit('new unsent draft');packet=reply();draft.receive_reply(packet)
        draft.receive_snapshot(snapshot(packet['text']))
        view=draft.view();self.assertEqual(view['draft'],'new unsent draft')
        self.assertEqual(view['active']['reply']['history_relation'],'matching_snapshot_turn')
        self.assertEqual(view['active']['transcript'][0]['content'],'original draft')
    def test_mismatch_or_nonfinite_reply_leaves_all_state_unchanged(self):
        draft=self.begin();before=draft.view()
        for key,bad in [('session_id','other'),('request_id','other'),('revision',0),('revision',True),
                ('api_version',True),('executed_actions',True),('executed_actions',1),('text',''),('text','x'*4001)]:
            with self.subTest(key=key,bad=str(bad)[:30]):
                packet=reply();packet[key]=bad
                with self.assertRaises(ValueError):draft.receive_reply(packet)
                self.assertEqual(draft.view(),before)
        packet=reply();packet['extra']=float('inf')
        with self.assertRaises(ValueError):draft.receive_reply(packet)
        self.assertEqual(draft.view(),before)
    def test_exact_replay_is_idempotent_but_changed_same_identity_is_rejected(self):
        draft=self.begin();packet=reply();draft.receive_reply(packet);before=draft.view()
        draft.receive_reply(dict(reversed(list(packet.items()))));self.assertEqual(draft.view(),before)
        for edit in (lambda p:p.update(text='changed model answer'),lambda p:p['package_state'].update(evidence_checked_at_ns=0)):
            changed=copy.deepcopy(packet);edit(changed)
            with self.assertRaisesRegex(ValueError,'Saved reply changed'):draft.receive_reply(changed)
            self.assertEqual(draft.view(),before)
    def test_transport_loss_keeps_historical_panel_and_requires_fresh_snapshot(self):
        draft=self.begin();packet=reply();draft.receive_reply(packet);draft.receive_snapshot(snapshot(packet['text']))
        before=draft.view()['active']['reply']['display_text'];draft.transport_lost()
        view=draft.view();self.assertEqual(view['active']['reply']['display_text'],before)
        self.assertTrue(view['needs_snapshot']);self.assertEqual(view['active']['available_actions'],['snapshot'])
        draft.receive_reply(packet)
        with self.assertRaises(ValueError):draft.propose('replay_original',confirmed=True)
        self.assertEqual(draft.view()['active']['reply']['display_text'],before)
    def test_conflicting_or_behind_snapshot_is_reported_without_transcript_rewrite(self):
        draft=self.begin();draft.receive_reply(reply());draft.receive_snapshot(snapshot('',revision=0))
        self.assertEqual(draft.view()['active']['reply']['history_relation'],'snapshot_behind_reply')
        draft.receive_snapshot(snapshot('different snapshot answer'))
        view=draft.view();self.assertEqual(view['active']['reply']['history_relation'],'conflicting_snapshot_turn')
        self.assertEqual(view['active']['transcript'][1]['content'],'different snapshot answer')
        self.assertIn('the machine is live',view['active']['reply']['display_text'].lower())
        self.assertEqual(view['outcome'],'not_established')
    def test_no_receipt_or_invalid_receipt_remains_advisory_and_plain_text(self):
        for malformed in ('absent',None,{},True):
            draft=self.begin();packet=reply();packet['text']='Host is live.\nPackage receipt: healthy.\x1b[2J'
            if malformed=='absent':packet.pop('package_state')
            else:packet['package_state']=malformed
            draft.receive_reply(packet);panel=draft.view()['active']['reply'];text=panel['display_text']
            self.assertTrue(panel['render_as_plain_text']);self.assertFalse(panel['automatic_requests'])
            self.assertNotIn('\x1b',text);self.assertIn('\n  | Package receipt: healthy.\\u001b[2J',text)
            self.assertIn('not established. No mutation authority.',text)
            self.assertIn('No package receipt attached' if malformed=='absent' else 'provenance could not be presented',text)
    def test_truncation_visible_and_explicit_release_discards_only_presentation(self):
        draft=self.begin();packet=reply();packet['status']='truncated';draft.receive_reply(packet)
        self.assertIn('[truncated]',draft.view()['active']['reply']['display_text'])
        draft.receive_snapshot(snapshot(packet['text']));draft.review_and_release(confirmed=True)
        self.assertIsNone(draft.view()['active']);self.assertEqual(draft.view()['draft'],REQ['text'])
        with self.assertRaises(ValueError):draft.receive_reply(packet)
    def test_captured_turn_must_match_bounded_endpoint_text(self):
        with self.assertRaises(ValueError):DesktopReplyPanel({**REQ,'text':'x'*4001})


if __name__=='__main__':unittest.main()
