"""Mocked helper branches only. No native worker or real signal is sent."""
import importlib.util,sys,signal,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'source'),str(HERE/'capsule-bridge')]
import gateway
class Lifecycle(unittest.TestCase):
    def test_deferred_cancellation_is_delivered_after_cleanup_window(self):
        class Cancelled(BaseException):pass
        seen=[]
        def handler(number,frame):seen.append(number);raise Cancelled()
        with self.assertRaises(Cancelled):gateway.replay_deferred_signal({signal.SIGTERM:handler},[signal.SIGTERM])
        self.assertEqual(seen,[signal.SIGTERM])
    def test_no_signal_is_no_op(self):gateway.replay_deferred_signal({},[])
    def test_ignored_handler_remains_ignored(self):gateway.replay_deferred_signal({signal.SIGTERM:signal.SIG_IGN},[signal.SIGTERM])
    def test_default_handler_becomes_bounded_interruption(self):
        with self.assertRaises(InterruptedError):gateway.replay_deferred_signal({signal.SIGTERM:signal.SIG_DFL},[signal.SIGTERM])
    def test_first_only_is_delivered(self):
        seen=[];handler=lambda n,f:seen.append(n)
        gateway.replay_deferred_signal({signal.SIGTERM:handler,signal.SIGALRM:handler},[signal.SIGTERM,signal.SIGALRM])
        self.assertEqual(seen,[signal.SIGTERM])
    def test_already_reaped_never_signaled(self):
        class P:returncode=0;pid=123
        with patch.object(gateway.os,'killpg',side_effect=AssertionError('Stale group signal forbidden')):
            self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'already-reaped')
    def test_lost_owner_never_signaled(self):
        class P:returncode=None;pid=123
        with patch.object(gateway,'observed_exit',side_effect=ChildProcessError()),patch.object(gateway.os,'killpg',side_effect=AssertionError('Lost ownership signal forbidden')):
            self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'lost')
    def test_owned_final_signal_before_wait(self):
        events=[]
        class P:
            returncode=None;pid=123
            def wait(self,timeout):events.append('reap');self.returncode=0;return 0
        with patch.object(gateway,'observed_exit',side_effect=lambda p:events.append('observe')),patch.object(gateway.os,'killpg',side_effect=lambda p,s:events.append('final-owned-signal')):
            self.assertTrue(gateway.stop_owned(P(),gateway.time.monotonic()+1)['reaped'])
        self.assertEqual(events,['observe','final-owned-signal','reap'])
if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('Native process forbidden')),patch('os.execve',side_effect=AssertionError('Native exec forbidden')):
        unittest.main(verbosity=2)
