"""Supervisor diagnostics with synthetic process results; no model inference."""
import unittest
from unittest.mock import Mock,patch
from test_fresh_utf8 import provider
import fresh
class ResourceDiagnostics(unittest.TestCase):
    def test_terminal_resource_reasons_keep_raw_evidence(self):
        for reason,exitcode,code in [('native-deadline',124,'native_timeout'),('native-tree-rss-cap',125,'resource_limit'),('host-available-reserve',125,'resource_limit'),('caller-cancelled-or-exited',125,'native_cancelled')]:
            p=provider();proc=Mock(pid=12345,returncode=exitcode)
            proc.communicate.return_value=(b'partial',f'ROKO_SUPERVISOR reason={reason} descendants_cleaned=1\n'.encode())
            with patch.object(fresh.subprocess,'Popen',return_value=proc):
                with self.assertRaisesRegex(fresh.GenerationError,code):p.chat([{'role':'user','content':'Hi'}])
            self.assertEqual(p.last_error,code);self.assertIsNone(p.last_generation)
            self.assertEqual(p.receipts[-1]['terminal_error'],code)
            self.assertEqual(p.receipts[-1]['stdout_bytes'],7)
    def test_wrong_exit_code_does_not_claim_resource_failure(self):
        p=provider();proc=Mock(pid=12345,returncode=0)
        proc.communicate.return_value=(b'',b'ROKO_SUPERVISOR reason=native-deadline descendants_cleaned=1\n')
        with patch.object(fresh.subprocess,'Popen',return_value=proc):
            with self.assertRaisesRegex(fresh.GenerationError,'missing_generation_receipt'):p.chat([{'role':'user','content':'Hi'}])
