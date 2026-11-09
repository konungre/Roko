"""Adversarial metadata/CLI tests; all constructed packets are fixtures."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_reply_view import render_reply,receipt_notice,load_packet,LIMITS
from test_package_reply_view import reply


class ReceiptUncertaintyTests(unittest.TestCase):
    def assert_uncertain(self,value):
        before=copy.deepcopy(value);notice=receipt_notice(value)
        self.assertIn('provenance could not be presented',notice)
        self.assertIn('Observation age unknown',notice);self.assertIn(LIMITS,notice)
        self.assertNotIn('revision 3',notice);self.assertNotIn('Source commit:',notice)
        self.assertEqual(before,value)
    def test_missing_or_invalid_reply_identity_cannot_bind_receipt(self):
        for key in ('session_id','request_id'):
            for invalid in (None,'','x\nLIVE',True,[],'a'*129):
                with self.subTest(key=key,invalid=invalid):
                    value=reply();value[key]=invalid;value['package_state']['binding'][key]=invalid
                    self.assert_uncertain(value)
            value=reply();value.pop(key);value['package_state']['binding'].pop(key)
            self.assert_uncertain(value)
    def test_partial_or_unknown_status_cannot_downgrade_to_strict_receipt(self):
        for invalid in (None,'fresh','live',[],{},True):
            value=reply();value['package_state']['evidence_status']=invalid
            self.assert_uncertain(value)
        value=reply();value['package_state'].pop('evidence_status');self.assert_uncertain(value)
    def test_invalid_or_contradictory_admission_metadata_is_neutral(self):
        changes=[('qualified_at_ns',None),('qualified_at_ns',True),('qualified_at_ns',-1),
            ('max_admission_age_seconds',0),('max_admission_age_seconds',True),
            ('max_admission_age_seconds',31536001),('evidence_checked_at_ns',False),
            ('evidence_checked_at_ns',-1),('admission_status','invented'),
            ('qualified_at_ns',0),('qualified_at_ns',1700000001000000000)]
        for key,invalid in changes:
            with self.subTest(key=key,invalid=invalid):
                value=reply();value['package_state'][key]=invalid;self.assert_uncertain(value)
        for key in ('qualified_at_ns','max_admission_age_seconds','evidence_checked_at_ns'):
            value=reply();value['package_state'].pop(key);self.assert_uncertain(value)
    def test_old_saved_valid_admission_stays_historical_not_reclassified_by_now(self):
        value=reply()
        with (patch('time.time',side_effect=AssertionError('No current clock query')),
              patch('time.time_ns',side_effect=AssertionError('No current clock query'))):
            notice=receipt_notice(value);view=render_reply(value)
        self.assertNotIn('provenance could not be presented',notice)
        self.assertIn('2023-11-14',notice);self.assertIn('at the recorded check',notice)
        self.assertIn('saved replay does not refresh evidence',notice)
        self.assertIn('Generated answer (package claims are advisory)',view)
    def test_boundary_valid_expired_and_backwards_clock_distinct(self):
        for delta,admission,status in [(3600000000000,'valid','available_freshness_unknown'),
                (3600000000001,'expired','admission_expired'),(-1,'clock_unverifiable','admission_clock_unverifiable')]:
            value=reply();state=value['package_state'];state.update(
                evidence_checked_at_ns=state['qualified_at_ns']+delta,admission_status=admission,evidence_status=status)
            if admission!='valid':state.update(data_admitted=False,source=None,query_receipt_sha256=None)
            notice=receipt_notice(value)
            self.assertNotIn('provenance could not be presented',notice)
            self.assertIn(LIMITS,notice);self.assertIn('not observation time',notice)
    def test_absent_null_and_empty_evidence_are_distinct_but_never_host_authority(self):
        value=reply();value.pop('package_state')
        self.assertIn('No package receipt attached',render_reply(value))
        for absent in (None,{},[],False,'unknown'):
            value=reply();value['package_state']=absent;self.assert_uncertain(value)
    def test_changed_commit_or_orphan_historical_proof_does_not_show_provenance(self):
        value=reply();value['package_state']['source_commit']='d'*40;self.assert_uncertain(value)
        value=reply();value['package_state'].update(evidence_status='source_missing',availability='missing',
            data_admitted=False,source=None,query_receipt_sha256=None,last_known_query_receipt_sha256='c'*64)
        self.assert_uncertain(value)
    def test_statuses_with_absent_data_explain_limitations_without_source(self):
        for availability in ('missing','inaccessible','unreadable','changed','invalid'):
            value=reply();value['package_state'].update(evidence_status='source_'+availability,availability=availability,
                data_admitted=False,source=None,query_receipt_sha256=None)
            notice=receipt_notice(value)
            self.assertNotIn('provenance could not be presented',notice);self.assertNotIn('Imported source:',notice)
            self.assertIn(LIMITS,notice);self.assertIn('not observation time',notice)
    def test_cli_rejects_duplicate_keys_nonfinite_and_oversized_packets_before_output(self):
        cli=Path(__file__).resolve().parents[1]/'package_reply_view.py'
        raw=json.dumps(reply())
        rows=[raw[:-1]+',"package_state":null}',raw.replace('"source_revision": 3','"source_revision": 3, "source_revision": 9'),
              raw.replace('"qualified_at_ns": 1700000000000000000','"qualified_at_ns": NaN'), ' '*131073+'\n']
        for row in rows:
            with self.subTest(prefix=row[:50]):
                proc=subprocess.run([sys.executable,'-B',str(cli)],input=row+'\n',text=True,capture_output=True)
                self.assertNotEqual(proc.returncode,0);self.assertEqual(proc.stdout,'')
        for raw in ('{"x":Infinity}','{"x":-Infinity}','{"x":NaN}','{"x":1,"x":2}'):
            with self.assertRaises(ValueError):load_packet(raw)


if __name__=='__main__':unittest.main()
