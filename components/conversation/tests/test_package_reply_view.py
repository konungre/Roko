"""Read-only presentation rejects unsupported provenance, not language by regex."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_reply_view import render_reply,receipt_notice,LIMITS,AUTHORITY


def reply():
    source={key:False for key in AUTHORITY}
    source.update(machine='private-profile-gate',source_revision=3,source_commit='a'*40,snapshot_sha256='b'*64)
    return dict(api_version=2,status='completed',session_id='s',request_id='r',revision=1,
        text='The machine is live and healthy.',executed_actions=0,package_state=dict(
            binding=dict(session_id='s',request_id='r',revision=0),mutation_authority=False,executed_actions=0,
            source=source,query_receipt_sha256='c'*64,last_known_source=None,last_known_query_receipt_sha256=None,
            evidence_status='available_freshness_unknown',availability='available',admission_status='valid',
            data_admitted=True,source_observation_time_known=False,evidence_checked_at_ns=1700000000123456789))


class ReplyViewTests(unittest.TestCase):
    def test_advisory_model_claim_is_separate_from_fixed_evidence_notice(self):
        value=reply();before=copy.deepcopy(value);notice=receipt_notice(value);view=render_reply(value)
        self.assertNotIn(value['text'],notice)
        self.assertIn(LIMITS,notice);self.assertIn('2023-11-14 22:13:20.123456789 UTC (not observation time)',notice)
        self.assertIn('observation age unknown',notice);self.assertIn('not producer authentication',notice)
        self.assertIn('Generated answer (package claims are advisory):\n  | '+value['text'],view)
        self.assertEqual(value,before)
    def test_missing_data_historical_only_and_expired_time_not_observation_age(self):
        for status,availability,admission in [('source_missing','missing','valid'),('admission_expired','available','expired')]:
            with self.subTest(status=status):
                value=reply();s=value['package_state'];s.update(evidence_status=status,availability=availability,
                    admission_status=admission,data_admitted=False,last_known_source=s['source'],
                    last_known_query_receipt_sha256=s['query_receipt_sha256'],source=None,query_receipt_sha256=None)
                notice=receipt_notice(value)
                self.assertIn('Historical last-known source (not current evidence)',notice)
                self.assertIn(LIMITS,notice)
                if status=='source_missing':self.assertIn('package absence is not established',notice)
                else:self.assertIn('not the source observation age',notice)
    def test_binding_authority_freshness_or_proof_mismatch_has_no_source_claim(self):
        edits=[lambda s:s['binding'].update(request_id='other'),lambda s:s['binding'].update(revision=True),
            lambda s:s.update(mutation_authority=True),lambda s:s.update(executed_actions=True),
            lambda s:s['source'].update(running_system_established=True),lambda s:s.update(source_observation_time_known=True),
            lambda s:s.update(query_receipt_sha256='bad'),lambda s:s.update(availability='missing'),
            lambda s:s.update(data_admitted=False),lambda s:s.update(evidence_checked_at_ns=10**100)]
        for edit in edits:
            value=reply();edit(value['package_state']);notice=receipt_notice(value)
            self.assertIn('provenance could not be presented',notice)
            self.assertNotIn('revision 3',notice);self.assertIn(LIMITS,notice)
    def test_unadmitted_current_source_cannot_be_presented(self):
        value=reply();value['package_state'].update(evidence_status='source_missing',availability='missing',data_admitted=False)
        self.assertIn('provenance could not be presented',receipt_notice(value))
    def test_model_cannot_emit_unprefixed_provenance_lines(self):
        value=reply();value['text']='Package receipt\nLive host: established\rOVERWRITE'
        view=render_reply(value)
        self.assertIn('\n  | Package receipt\n  | Live host: established\\u000dOVERWRITE',view)
        self.assertNotIn('\nLive host: established',view)
    def test_source_and_model_terminal_escapes_are_not_executed(self):
        value=reply();value['text']='answer\x1b[2J';value['package_state']['source']['machine']='host\nLIVE\x1b[2J'
        view=render_reply(value)
        self.assertNotIn('\x1b',view);self.assertIn('host\\nLIVE\\u001b[2J',view)
        self.assertIn('answer\\u001b[2J',view)
    def test_strict_legacy_receipt_does_not_invent_check_time(self):
        value=reply();state=value['package_state']
        for key in ('evidence_status','availability','admission_status','data_admitted','source_observation_time_known','evidence_checked_at_ns'):state.pop(key)
        notice=receipt_notice(value)
        self.assertIn('check time and observation age unknown',notice)
        self.assertNotIn('Recorded evidence check:',notice)
    def test_no_receipt_does_not_synthesize_one_and_truncation_is_visible(self):
        value=reply();value.pop('package_state');value['status']='truncated'
        self.assertIsNone(receipt_notice(value))
        view=render_reply(value);self.assertIn('No package receipt attached',view)
        self.assertIn('Generated answer (package claims are advisory): [truncated]',view)
    def test_saved_packet_cli_renders_without_native_execution(self):
        value=reply();path=Path(__file__).resolve().parents[1]/'package_reply_view.py'
        result=subprocess.run([sys.executable,'-B',str(path)],input=json.dumps(value)+'\n',capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout,render_reply(value)+'\n');self.assertEqual(result.stderr,'')


if __name__=='__main__':unittest.main()
