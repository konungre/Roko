"""Motto RPC/receipt faults with process doubles; native probe is separate."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motto
import conversation
import durable_api


class MottoTests(unittest.TestCase):
    def run_case(self, *, wrong=False, primary=None, cleanup_error=False, write_error=False):
        messages = [{'role':'user','content':'hello'}]
        binding = {'session_id':'s','request_id':'r','revision':0}
        digest = motto.hashlib.sha256(motto.canonical({'binding':binding,'messages':messages})).hexdigest()
        wire = motto.canonical({'stage':'model_request','messages':[] if wrong else messages,
                                'snapshot_sha256':digest}) + b'\n'
        response = motto.canonical({'stage':'completed','text':'native fixture','snapshot_sha256':digest})
        proc = SimpleNamespace(stdin=Mock(),stdout=Mock(),stderr=Mock(),returncode=0,
            poll=Mock(return_value=0),terminate=Mock(),kill=Mock(),wait=Mock(),
            communicate=Mock(return_value=(response,b'descendants_cleaned=1')))
        proc.stdin.write.side_effect=lambda data:len(data)
        model = Mock(return_value='native fixture',side_effect=primary)
        if cleanup_error:
            proc.poll.side_effect=OSError('poll fault')
            proc.terminate.side_effect=OSError('terminate fault')
        with tempfile.TemporaryDirectory() as root:
            provider = SimpleNamespace(chat=model,profile={'python':sys.executable,
                'motto_transport':{'python':sys.executable,'guard_manifest':'synthetic',
                    'guard_admission':'synthetic','evidence_root':root}})
            transport = motto.MottoTransport(provider)
            writer = motto.write_record
            def write(path, value):
                if write_error and path.name=='receipt.json':
                    raise OSError('receipt fault')
                writer(path,value)
            error = None
            with patch.object(durable_api,'current',{'session_id':'s','request_id':'r','revision':0}), \
                 patch.object(conversation,'session',SimpleNamespace(history=[])), \
                 patch.object(motto.subprocess,'Popen',return_value=proc), \
                 patch.object(motto.select,'select',return_value=([proc.stdout],[],[])), \
                 patch.object(motto.os,'read',side_effect=[bytes([b]) for b in wire]), \
                 patch.object(motto,'write_record',side_effect=write):
                try:
                    self.assertEqual(transport.chat(messages),'native fixture')
                except BaseException as caught:
                    error=caught
            receipt=transport.receipts[0]
            if not write_error:
                self.assertEqual(json.loads(next(Path(root).rglob('receipt.json')).read_bytes()),receipt)
            if error is not None:
                self.assertIs(error.receipt,receipt)
            return error,receipt,model,proc

    def test_exact_model_input_and_receipt(self):
        error,receipt,model,proc=self.run_case()
        self.assertIsNone(error);self.assertEqual(receipt['status'],'passed')
        model.assert_called_once_with([{'role':'user','content':'hello'}])
        proc.wait.assert_called_once()

    def test_changed_handshake_does_not_call_model(self):
        error,receipt,model,_=self.run_case(wrong=True)
        self.assertIsInstance(error,ValueError);model.assert_not_called()
        self.assertEqual(receipt['status'],'failed')

    def test_original_cancellation_survives_cleanup_fault(self):
        primary=KeyboardInterrupt('cancel')
        error,receipt,_,proc=self.run_case(primary=primary,cleanup_error=True)
        self.assertIs(error,primary)
        self.assertIn('terminate',[row['stage'] for row in receipt['finalization_errors']])
        proc.kill.assert_called_once()

    def test_failed_receipt_write_withholds_success(self):
        error,receipt,_,_=self.run_case(write_error=True)
        self.assertIsInstance(error,OSError);self.assertEqual(receipt['status'],'failed')

    def test_failed_receipt_write_preserves_cancellation(self):
        primary=KeyboardInterrupt('cancel')
        error,receipt,_,_=self.run_case(primary=primary,write_error=True)
        self.assertIs(error,primary)
        self.assertEqual(receipt['finalization_errors'][-1]['stage'],'receipt-write')


if __name__=='__main__':
    unittest.main()
