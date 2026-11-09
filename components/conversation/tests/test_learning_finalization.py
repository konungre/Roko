"""Process doubles only: cancellation and cleanup faults must retain receipts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import learning

REQUEST={'version':1,'request_id':'fixture','operation':'rank_proposals',
    'state':{'goals':[.5]*8,'modulators':[.5]*6},
    'candidates':[{'id':'first','correlations':[.1]*8,'risk':.1,'delta_goals':[0]*8}]}


class FinalizationTests(unittest.TestCase):
    def process(self):
        return SimpleNamespace(returncode=None,poll=Mock(return_value=None),terminate=Mock(),kill=Mock(),
            wait=Mock(return_value=-9),communicate=Mock(),
            stdin=Mock(),stdout=Mock(),stderr=Mock())
    def run_failed(self,proc,primary,*,writer_fault=False):
        with tempfile.TemporaryDirectory() as tmp:
            config={'evidence_root':tmp,'guard_manifest':'/synthetic/guard','guard_admission':'synthetic',
                    'components':{'metamo':{'manifest':'/synthetic/manifest','sha256':'synthetic'}}}
            learner=learning.LearningComponents({'python':sys.executable,'learning_components':config})
            original=learning.write_record
            def writer(path,record):
                if writer_fault and path.name=='receipt.json':raise OSError('synthetic receipt write')
                return original(path,record)
            with patch.object(learning.subprocess,'Popen',return_value=proc),patch.object(learning,'write_record',side_effect=writer):
                with self.assertRaises(type(primary)) as caught:
                    learner.run_turn([{'component':'metamo','request':REQUEST}],'Synthetic request',[],
                        {'session_id':'s','request_id':'r','revision':0})
            self.assertIs(caught.exception,primary)
            self.assertEqual(len(learner.receipts),1)
            receipt=learner.receipts[0]
            self.assertIs(caught.exception.receipt,receipt)
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['executed_actions'],0)
            if not writer_fault:
                path=Path(receipt['evidence_directory'])/'receipt.json'
                self.assertEqual(json.loads(path.read_bytes()),receipt)
            for name in ('stdin','stdout','stderr'):getattr(proc,name).close.assert_called_once()
            proc.wait.assert_called_once_with(timeout=2)
            return receipt

    def test_keyboard_interrupt_and_terminate_error_keep_primary_and_receipt(self):
        proc=self.process();primary=KeyboardInterrupt('cancel')
        proc.communicate.side_effect=[primary,(b'partial stdout',b'partial stderr'),(b'partial stdout',b'partial stderr')]
        proc.terminate.side_effect=OSError('terminate broke')
        receipt=self.run_failed(proc,primary)
        self.assertEqual(receipt['stdout'],'partial stdout');self.assertEqual(receipt['stderr'],'partial stderr')
        self.assertIn('terminate',[e['stage'] for e in receipt['finalization_errors']])
        proc.kill.assert_called_once()

    def test_poll_terminate_kill_wait_and_all_closes_fail_independently(self):
        proc=self.process();primary=KeyboardInterrupt('primary')
        proc.poll.side_effect=OSError('poll broke');proc.terminate.side_effect=OSError('terminate broke')
        proc.kill.side_effect=OSError('kill broke');proc.wait.side_effect=OSError('wait broke')
        proc.communicate.side_effect=[primary,RuntimeError('drain broke'),(b'last bytes',b'diagnostic')]
        for name in ('stdin','stdout','stderr'):getattr(proc,name).close.side_effect=OSError(name+' close broke')
        receipt=self.run_failed(proc,primary)
        stages={e['stage'] for e in receipt['finalization_errors']}
        self.assertTrue({'poll-before-terminate','terminate','communicate-after-terminate','poll-before-kill','kill','wait',
            'stream-close:stdin','stream-close:stdout','stream-close:stderr'}<=stages)
        self.assertEqual(receipt['stdout'],'last bytes')
        proc.terminate.assert_called_once();proc.kill.assert_called_once()

    def test_final_communicate_timeout_retains_partial_binary_output(self):
        proc=self.process();primary=KeyboardInterrupt('primary')
        primary.output=b'head\xff';primary.stderr=b'error'
        proc.communicate.side_effect=[primary,
            subprocess.TimeoutExpired('synthetic',5,output=b'head\xff more',stderr=b'error more'),
            subprocess.TimeoutExpired('synthetic',3,output=b'head\xff more final',stderr=b'error more final')]
        receipt=self.run_failed(proc,primary)
        self.assertEqual(bytes.fromhex(receipt['stdout_hex']),b'head\xff more final')
        self.assertEqual(bytes.fromhex(receipt['stderr_hex']),b'error more final')
        self.assertEqual(len(receipt['output_fragments']),3)
        self.assertIn('communicate-after-kill',[e['stage'] for e in receipt['finalization_errors']])

    def test_second_cancellation_during_cleanup_does_not_replace_primary(self):
        proc=self.process();primary=KeyboardInterrupt('first cancellation')
        proc.communicate.side_effect=[primary,SystemExit('cleanup cancellation'),(b'final',b'')]
        receipt=self.run_failed(proc,primary)
        self.assertEqual(receipt['error'],repr(primary))
        self.assertEqual(receipt['finalization_errors'][0]['type'],'SystemExit')

    def test_receipt_write_fault_keeps_primary_and_attached_memory_evidence(self):
        proc=self.process();primary=KeyboardInterrupt('primary')
        proc.communicate.side_effect=[primary,(b'output',b''),(b'output',b'')]
        receipt=self.run_failed(proc,primary,writer_fault=True)
        self.assertEqual(receipt['stdout'],'output')
        self.assertEqual(receipt['finalization_errors'][-1]['stage'],'receipt-write')

    def test_successful_drain_does_not_erase_initial_timeout_bytes(self):
        proc=self.process();primary=subprocess.TimeoutExpired('synthetic',40,output=b'partial',stderr=b'err')
        proc.communicate.side_effect=[primary,(b'',b''),(b'',b'')]
        receipt=self.run_failed(proc,primary)
        self.assertEqual(receipt['stdout'],'partial');self.assertEqual(receipt['stderr'],'err')

    def test_already_exited_child_is_not_signalled(self):
        proc=self.process();proc.poll.return_value=0;proc.returncode=0
        primary=ValueError('bad packet')
        proc.communicate.side_effect=[primary,(b'recovered',b'diagnostic')]
        self.run_failed(proc,primary)
        proc.terminate.assert_not_called();proc.kill.assert_not_called()

    def test_success_with_close_fault_becomes_failed(self):
        proc=self.process();proc.returncode=0
        result={'selected_proposal_id':'first','scores':[]}
        packet={'component':'metamo','request_sha256':learning.digest(REQUEST),'receipt':{'status':'passed'},'response':result}
        proc.communicate.return_value=(learning.canonical(packet),b'descendants_cleaned=1')
        primary=OSError('stdout close broke');proc.stdout.close.side_effect=primary
        receipt=self.run_failed(proc,primary)
        self.assertEqual(receipt['finalization_errors'][0]['stage'],'stream-close:stdout')
        self.assertNotIn('response',receipt)

if __name__=='__main__':unittest.main()
