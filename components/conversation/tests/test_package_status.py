"""Real data-file availability/clock policy with explicitly doubled native queries."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import package_awareness as awareness
import package_status as status
import test_package_awareness as base
from components.os_atomspace import conversation_gateway as gateway


class StatusTests(base.ReceiptCacheTests):
    def setUp(self):
        super().setUp()
        old=self.observer
        self.observer=status.ReceiptStatusAwareness.__new__(status.ReceiptStatusAwareness)
        self.observer.__dict__.update(old.__dict__)
        root=Path(self.temp.name)
        self.facts=root/'facts.json';self.data=root/'receipts.json'
        self.facts.write_text('{}');self.data.write_text('{}')
        self.observer.manifest.update(facts_path=str(self.facts),receipts_path=str(self.data),
            files={str(path):awareness.sha(path) for path in (self.facts,self.data)})
        self.manifest.write_text(json.dumps(self.observer.manifest))
        self.observer.config.update(sha256=awareness.sha(self.manifest),receipt_policy='explain_v1',
                                   qualified_at_ns=100000000000,max_admission_age_seconds=10)
        self.runtime=patch.object(gateway,'verify_runtime');self.runtime.start()
        self.parser=patch.object(gateway,'parse_source',return_value=self.packet);self.parser.start()
        self.clock=patch.object(status.time,'time_ns',return_value=101000000000);self.clock.start()
    def tearDown(self):
        self.clock.stop();self.parser.stop();self.runtime.stop();super().tearDown()
    # Inherited strict-policy assertions are exercised by ReceiptCacheTests;
    # these named cases cover only the opt-in status policy.
    def test_native_query_is_cached_but_each_turn_is_bound(self):
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=self.query) as query:
            first=self.stage();second=self.stage('next')
        self.assertEqual(query.call_count,1)
        self.assertTrue(first['state']['data_admitted']);self.assertTrue(second['state']['query_reused'])
        self.assertFalse(first['state']['source_observation_time_known'])
    def test_changed_cached_receipt_fails_before_context_return(self):
        super().test_changed_cached_receipt_fails_before_context_return()
    def test_source_manifest_drift_fails_without_query(self):
        super().test_source_manifest_drift_fails_without_query()
    def test_incorrect_authority_result_is_not_cached(self):
        super().test_incorrect_authority_result_is_not_cached()
    def test_missing_data_is_not_package_absence_and_cached_source_is_historical(self):
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=self.query) as query:
            self.stage();self.data.unlink();limited=self.stage('missing')
        self.assertEqual(query.call_count,1)
        self.assertEqual(limited['state']['evidence_status'],'source_missing')
        self.assertIsNone(limited['state']['source']);self.assertIsNotNone(limited['state']['last_known_source'])
        self.assertFalse(limited['state']['data_admitted'])
        self.assertIn('does not imply packages are absent',limited['context'][0]['text'])
        self.assertIn('historical',limited['context'][0]['text'])
    def test_expired_admission_is_not_an_observation_timestamp(self):
        with patch.object(status.time,'time_ns',return_value=111000000000),patch.object(gateway,'run') as query:
            limited=self.stage()
        query.assert_not_called()
        self.assertEqual(limited['state']['evidence_status'],'admission_expired')
        self.assertFalse(limited['state']['source_observation_time_known'])
        self.assertIsNone(limited['state']['source'])
        self.assertIn('not the source observation time',limited['context'][0]['text'])
    def test_changed_source_is_not_parsed_or_used(self):
        self.data.write_text('unqualified changed bytes')
        with patch.object(gateway,'parse_source') as parse,patch.object(gateway,'run') as query:
            limited=self.stage()
        parse.assert_not_called();query.assert_not_called()
        self.assertEqual(limited['state']['evidence_status'],'source_changed')
    def test_runtime_integrity_failure_is_not_degraded(self):
        with patch.object(gateway,'verify_runtime',side_effect=ValueError('runtime changed')),self.assertRaises(ValueError):self.stage()
    def test_fifo_source_is_unreadable_without_waiting_for_a_writer(self):
        self.data.unlink();os.mkfifo(self.data)
        with patch.object(gateway,'run') as query:limited=self.stage()
        query.assert_not_called();self.assertEqual(limited['state']['evidence_status'],'source_unreadable')
    def test_cancellation_is_not_converted_to_a_status_answer(self):
        primary=KeyboardInterrupt('cancel')
        with patch.object(gateway,'verify_profile',return_value=self.packet),patch.object(gateway,'run',side_effect=primary),self.assertRaises(KeyboardInterrupt) as caught:
            self.stage()
        self.assertIs(caught.exception,primary)
        self.assertEqual(self.observer.receipts[-1]['status'],'failed')
    def test_clock_before_qualification_does_not_admit_source(self):
        with patch.object(status.time,'time_ns',return_value=99000000000):limited=self.stage()
        self.assertEqual(limited['state']['evidence_status'],'admission_clock_unverifiable')
        self.assertFalse(limited['state']['data_admitted'])
    def test_data_required_by_base_profile_cannot_become_optional(self):
        profile={'package_awareness':self.observer.config,'files':{
            str(self.manifest):awareness.sha(self.manifest),str(self.data):awareness.sha(self.data)}}
        with self.assertRaisesRegex(ValueError,'also mandatory'):status.validate_status_profile(profile)


if __name__=='__main__':unittest.main()
