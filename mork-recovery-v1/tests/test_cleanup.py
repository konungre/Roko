"""Actual owned helper processes, never MORK/SWI or downloaded code."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
import native_mork as m


class CleanupTests(unittest.TestCase):
    def helper(self, code):
        return subprocess.Popen([sys.executable, '-B', '-c', code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True)

    def test_exited_leader_remains_owned_until_final_signal(self):
        process = self.helper('raise SystemExit(0)')
        try:
            deadline = time.monotonic() + 2
            while m._observed_exit(process) is None:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.005)
            self.assertIsNone(process.returncode)
            real_kill = os.killpg
            def signal_owned(pid, sig):
                self.assertIsNone(process.returncode)
                self.assertIsNotNone(m._observed_exit(process))
                return real_kill(pid, sig)
            with patch.object(m.os, 'killpg', side_effect=signal_owned) as kill:
                m._cleanup(process)
                kill.assert_called_once_with(process.pid, signal.SIGKILL)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.returncode is None: m._cleanup(process)

    def test_already_reaped_never_signaled(self):
        process = SimpleNamespace(returncode=0, pid=123456)
        with patch.object(m.os, 'killpg') as kill:
            with self.assertRaisesRegex(m.NativeMORKError, 'ownership'):
                m._kill(process)
            kill.assert_not_called()

    def test_lost_ownership_never_signaled(self):
        process = SimpleNamespace(returncode=None, pid=123456)
        with patch.object(m.os, 'waitid', side_effect=ChildProcessError), \
             patch.object(m.os, 'killpg') as kill:
            with self.assertRaisesRegex(m.NativeMORKError, 'ownership'):
                m._kill(process)
            kill.assert_not_called()

    def test_reap_timeout_is_bounded_failure(self):
        process = SimpleNamespace(returncode=None, pid=123456)
        process.wait = lambda timeout: (_ for _ in ()).throw(subprocess.TimeoutExpired('helper', timeout))
        with patch.object(m, '_observed_exit', return_value=None), patch.object(m.os, 'killpg'):
            with self.assertRaisesRegex(m.NativeMORKError, 'reap timed out'):
                m._kill(process)

    def test_first_cleanup_signal_replayed_after_reap_and_close(self):
        process = self.helper('import time;time.sleep(10)')
        saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        seen = []
        def callback(number, frame):
            seen.append(number)
            self.assertIsNotNone(process.returncode)
            self.assertTrue(all(p.closed for p in (process.stdin, process.stdout, process.stderr)))
        for s in saved: signal.signal(s, callback)
        original = m._kill
        def cancel_during_cleanup(child):
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGINT)
            self.assertEqual(seen, [])
            original(child)
        try:
            with patch.object(m, '_kill', side_effect=cancel_during_cleanup):
                m._cleanup(process)
            self.assertEqual(seen, [signal.SIGTERM])
            self.assertIs(signal.getsignal(signal.SIGTERM), callback)
        finally:
            for s, h in saved.items(): signal.signal(s, h)
            if process.returncode is None: m._cleanup(process)

    def test_default_signal_not_dropped(self):
        with self.assertRaises(InterruptedError):
            m._replay_deferred({signal.SIGTERM: signal.SIG_DFL}, [signal.SIGTERM])

    def test_keyboard_interrupt_not_dropped(self):
        with self.assertRaises(KeyboardInterrupt):
            m._replay_deferred({signal.SIGINT: signal.default_int_handler}, [signal.SIGINT])

    def test_ignored_signal_stays_ignored(self):
        m._replay_deferred({signal.SIGTERM: signal.SIG_IGN}, [signal.SIGTERM])

    def test_nonmain_call_rejected_before_spawn(self):
        errors = []
        def call():
            try: m._run(['unused'], b'', cwd='.', env={}, timeout=1)
            except BaseException as error: errors.append(error)
        with patch.object(m.subprocess, 'Popen') as spawn:
            worker = threading.Thread(target=call)
            worker.start(); worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            spawn.assert_not_called()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], m.NativeMORKError)

    def test_success_reaps_only_after_final_group_signal(self):
        events = []
        real_kill, real_wait = os.killpg, subprocess.Popen.wait
        def kill(pid, sig):
            events.append('signal')
            return real_kill(pid, sig)
        def wait(process, *args, **kwargs):
            events.append('reap')
            return real_wait(process, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(m.os, 'killpg', side_effect=kill), \
             patch.object(subprocess.Popen, 'wait', new=wait):
            output = m._run([sys.executable, '-B', '-c', 'print("ok")'], b'x\n',
                            cwd=directory, env={'PATH': '/usr/bin:/bin'}, timeout=2)
        self.assertEqual(output, b'ok\n')
        self.assertEqual(events, ['signal', 'reap'])


if __name__ == '__main__': unittest.main()
