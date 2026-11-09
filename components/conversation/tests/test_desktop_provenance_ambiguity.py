"""Ambiguous frame/evidence cannot silently replace accepted local choices."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from test_desktop_reply import REQ,snapshot
from test_package_reply_view import reply


class DisclosureAmbiguityTests(unittest.TestCase):
    def begin(self,packet=None):
        state=DesktopDraft(REQ['text']);state.begin(REQ,confirmed=True)
        if packet is not None:state.receive_reply_line(json.dumps(packet)+'\n')
        return state
    def test_ambiguous_nonfinite_and_partial_frames_preserve_accepted_open_panel(self):
        packet=reply();state=self.begin(packet);state.edit('unsent text');state.set_provenance_details_visible(True)
        before=state.view();raw=json.dumps(packet)
        bad=[raw[:-1]+',"package_state":null}',raw.replace('"source_revision": 3','"source_revision": 3,"source_revision": 4'),
            raw[:-1]+',"extra":1e999}',raw[:-1]+',"extra":NaN}',raw[:30],raw+'\n'+raw,' '*131073,
            None,raw.encode('utf-8'),raw[:-1]+',"nested":'+'['*1200+'0'+']'*1200+'}']
        for frame in bad:
            with self.subTest(frame=str(frame)[:45]):
                with self.assertRaises(ValueError):state.receive_reply_line(frame)
                self.assertEqual(state.view(),before)
    def test_partial_first_frame_never_creates_reply_and_complete_frame_is_explicit(self):
        state=self.begin();before=state.view();raw=json.dumps(reply())
        with self.assertRaises(ValueError):state.receive_reply_line(raw[:20])
        self.assertEqual(state.view(),before);self.assertIsNone(state.view()['active']['reply'])
        state.receive_reply_line(raw);self.assertIsNotNone(state.view()['active']['reply'])
        self.assertTrue(state.view()['needs_snapshot'])
    def test_incomplete_provenance_cannot_silently_upgrade_same_saved_identity(self):
        incomplete=reply();incomplete['package_state'].pop('query_receipt_sha256')
        state=self.begin(incomplete);state.set_provenance_details_visible(True);before=state.view()
        detail=before['active']['reply']['provenance']['details_text']
        self.assertIn('provenance could not be presented',detail);self.assertNotIn('Source commit:',detail)
        with self.assertRaisesRegex(ValueError,'Saved reply changed'):state.receive_reply_line(json.dumps(reply()))
        self.assertEqual(state.view(),before)
    def test_missing_fields_remain_uncertain_in_both_disclosure_states(self):
        for section,key in [('state','binding'),('state','evidence_checked_at_ns'),('state','max_admission_age_seconds'),
                ('state','query_receipt_sha256'),('source','machine'),('source','snapshot_sha256'),('source','producer_authenticated')]:
            with self.subTest(section=section,key=key):
                packet=reply();target=packet['package_state'] if section=='state' else packet['package_state']['source'];target.pop(key)
                state=self.begin(packet);before=state.view();summary=before['active']['reply']['provenance']['summary_text']
                self.assertIn('provenance could not be presented',summary);self.assertIn('Source observation age: unknown.',summary)
                state.set_provenance_details_visible(True);view=state.view()['active']['reply']['provenance']
                self.assertIn('provenance could not be presented',view['details_text']);self.assertNotIn('Source commit:',view['details_text'])
                self.assertEqual(summary,view['summary_text']);self.assertFalse(view['mutation_authority'])
                state.set_provenance_details_visible(False);self.assertEqual(state.view(),before)
    def test_local_inspection_never_reads_receipt_paths_or_spawns_requests(self):
        packet=reply();packet['package_state']['receipt_path']='/not/a/receipt/to/read'
        packet['package_state']['source']['facts_path']='/not/a/host/file'
        state=self.begin(packet)
        with (patch('builtins.open',side_effect=AssertionError('No file reads')),
              patch('pathlib.Path.read_bytes',side_effect=AssertionError('No source reads')),
              patch('subprocess.run',side_effect=AssertionError('No process')),
              patch('socket.socket',side_effect=AssertionError('No network')),
              patch.object(state,'propose',side_effect=AssertionError('No request proposal'))):
            state.set_provenance_details_visible(True);view=state.view()
            state.set_provenance_details_visible(False)
        detail=view['active']['reply']['provenance']['details_text']
        self.assertIn('Service-reported provenance',detail);self.assertNotIn('/not/a',detail)
        self.assertIn('not producer authentication',detail)
    def test_error_and_bad_snapshot_do_not_reset_choice_or_unblock_actions(self):
        packet=reply();state=self.begin(packet);state.set_provenance_details_visible(True)
        state.receive_error(dict(api_version=2,status='error',code='busy',session_id='s',request_id='r'))
        before=state.view();bad=snapshot(packet['text']);bad.pop('pending')
        with self.assertRaises(ValueError):state.receive_snapshot(bad)
        self.assertEqual(state.view(),before);self.assertTrue(before['needs_snapshot'])
        self.assertTrue(before['active']['reply']['provenance']['details_expanded'])
        self.assertEqual(before['active']['available_actions'],['snapshot'])
        with self.assertRaises(ValueError):state.propose('recover_pending',confirmed=True,owner_stopped=True)
    def test_legacy_receipt_does_not_invent_time_on_disclosure(self):
        packet=reply();metadata=packet['package_state']
        for key in ('evidence_status','availability','admission_status','data_admitted','source_observation_time_known',
                'evidence_checked_at_ns','qualified_at_ns','max_admission_age_seconds'):metadata.pop(key)
        state=self.begin(packet);state.set_provenance_details_visible(True);view=state.view()['active']['reply']['provenance']
        for text in (view['summary_text'],view['details_text']):
            self.assertIn('check time and observation age unknown',text);self.assertNotIn('Recorded evidence check:',text)
        self.assertFalse(view['source_check_refreshed'])
    def test_release_then_new_identity_can_show_new_reply_without_rewriting_prior_one(self):
        packet=reply();packet['package_state']=None;state=self.begin(packet)
        state.set_provenance_details_visible(True);prior=copy.deepcopy(state.view()['active']['reply'])
        state.receive_snapshot(snapshot(packet['text']));state.review_and_release(confirmed=True)
        state.edit('new explicit turn');request={**REQ,'request_id':'new','expected_revision':1,'text':'new explicit turn'}
        state.begin(request,confirmed=True);new=reply();new.update(request_id='new',revision=2)
        new['package_state']['binding'].update(request_id='new',revision=1)
        state.receive_reply_line(json.dumps(new));current=state.view()['active']['reply']
        self.assertFalse(current['provenance']['details_expanded']);self.assertNotIn('provenance could not be presented',current['provenance']['summary_text'])
        self.assertIn('provenance could not be presented',prior['provenance']['summary_text'])
        self.assertEqual(prior['request_id'],'r');self.assertEqual(current['request_id'],'new')


if __name__=='__main__':unittest.main()
