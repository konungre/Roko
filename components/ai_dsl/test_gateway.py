"""Gateway failure receipts with explicit process doubles, not native claims."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import gateway


class GatewayFailures(unittest.TestCase):
    def test_primary_cancellation_and_receipt_survive_terminate_failure(self):
        primary=KeyboardInterrupt('synthetic cancellation');primary.output=b'partial\xff'
        proc=SimpleNamespace(returncode=None,poll=Mock(return_value=None),
            terminate=Mock(side_effect=OSError('terminate fault')),kill=Mock(),wait=Mock(),
            stdin=Mock(),stdout=Mock(),stderr=Mock(),
            communicate=Mock(side_effect=[primary,(b'partial\xff',b'error'),(b'partial\xff final',b'error')]))
        with tempfile.TemporaryDirectory() as directory:
            profile={'python':sys.executable,'evidence_root':directory,'guard_manifest':'synthetic','guard_admission':'synthetic'}
            with patch.object(gateway,'verify_profile',return_value={'prlimit':'/usr/bin/prlimit','python':sys.executable}), \
                 patch.object(gateway.subprocess,'Popen',return_value=proc),self.assertRaises(KeyboardInterrupt) as caught:
                gateway.run({'version':1,'goal':'speech_to_text','depth':0},profile)
            self.assertIs(caught.exception,primary)
            receipt=json.loads(next(Path(directory).rglob('receipt.json')).read_bytes())
            self.assertEqual(receipt,primary.receipt);self.assertEqual(receipt['status'],'failed')
            self.assertEqual(bytes.fromhex(receipt['stdout_hex']),b'partial\xff final')
            self.assertIn('terminate',[row['stage'] for row in receipt['finalization_errors']])
            self.assertNotIn('response',receipt);proc.kill.assert_called_once();proc.wait.assert_called_once()

    def test_spawn_failure_retains_receipt(self):
        primary=OSError('synthetic spawn failure')
        with tempfile.TemporaryDirectory() as directory:
            profile={'python':sys.executable,'evidence_root':directory,'guard_manifest':'synthetic','guard_admission':'synthetic'}
            with patch.object(gateway,'verify_profile',return_value={'prlimit':'/usr/bin/prlimit','python':sys.executable}), \
                 patch.object(gateway.subprocess,'Popen',side_effect=primary),self.assertRaises(OSError) as caught:
                gateway.run({'version':1,'goal':'speech_to_text','depth':0},profile)
            self.assertIs(caught.exception,primary)
            receipt=json.loads(next(Path(directory).rglob('receipt.json')).read_bytes())
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['executed_services'],0)


if __name__=='__main__':unittest.main()
