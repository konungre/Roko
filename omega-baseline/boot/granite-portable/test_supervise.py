"""Harmless process-tree tests. Never loads a model or boots a guest."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_supervise', HERE / 'supervise.py')
supervise = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervise)


def command(seconds, child):
    return [sys.executable, str(HERE / 'supervise.py'), '--parent-pid', str(os.getpid()),
            '--parent-start', str(supervise.process(os.getpid())['start']),
            '--seconds', str(seconds), '--', *child]


def running(pid):
    row = supervise.process(pid)
    return bool(row and row['state'] != 'Z')


class SupervisionTests(unittest.TestCase):
    def test_normal_exit_and_output(self):
        p = subprocess.run(command(2, [sys.executable, '-c', 'print("inert")']),
                           start_new_session=True, capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, 'inert\n')
        self.assertIn('descendants_cleaned=1', p.stderr)

    def test_timeout_kills_helper_and_new_session_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pids.json'
            body = 'import subprocess,sys,time,os,json; from pathlib import Path; c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True); Path(sys.argv[1]).write_text(json.dumps([os.getpid(),c.pid])); time.sleep(30)'
            p = subprocess.run(command(.4, [sys.executable, '-c', body, str(path)]),
                               start_new_session=True, capture_output=True, text=True, timeout=5)
            self.assertEqual(p.returncode, 124, p.stderr)
            self.assertIn('native-deadline', p.stderr)
            self.assertTrue(path.exists())
            self.assertTrue(all(not running(pid) for pid in json.loads(path.read_text())))

    def test_main_exit_cleans_escaped_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pid'
            body = 'import subprocess,sys; from pathlib import Path; c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True); Path(sys.argv[1]).write_text(str(c.pid))'
            p = subprocess.run(command(2, [sys.executable, '-c', body, str(path)]),
                               start_new_session=True, capture_output=True, text=True, timeout=5)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse(running(int(path.read_text())))

    def test_cli_group_cancellation_cleans_native_and_escaped_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pids.json'
            parent = '''import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import supervise
body='import subprocess,sys,time,os,json; from pathlib import Path; c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True); Path(sys.argv[1]).write_text(json.dumps([os.getpid(),c.pid])); time.sleep(30)'
cmd=[sys.executable,sys.argv[1]+'/supervise.py','--parent-pid',str(os.getpid()),'--parent-start',str(supervise.process(os.getpid())['start']),'--seconds','20','--',sys.executable,'-c',body,sys.argv[2]]
p=subprocess.Popen(cmd,start_new_session=True)
Path(sys.argv[2]+'.supervisor').write_text(str(p.pid));time.sleep(30)
'''
            cli = subprocess.Popen([sys.executable, '-c', parent, str(HERE), str(path)],
                                   start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                end = time.monotonic() + 3
                while not path.exists() and time.monotonic() < end:
                    time.sleep(.02)
                self.assertTrue(path.exists())
                ids = json.loads(path.read_text()) + [int(Path(str(path)+'.supervisor').read_text())]
                os.killpg(cli.pid, signal.SIGKILL)
                cli.wait(timeout=2)
                end = time.monotonic() + 2
                while any(running(pid) for pid in ids) and time.monotonic() < end:
                    time.sleep(.02)
                self.assertTrue(all(not running(pid) for pid in ids), ids)
                self.assertTrue(running(os.getpid()), 'Caller test process must survive')
            finally:
                if cli.poll() is None:
                    os.killpg(cli.pid, signal.SIGKILL)
                    cli.wait(timeout=2)

    def test_failure_isolation_and_wrong_session(self):
        # Never signal our own process group when no separate supervisor session exists.
        p = subprocess.run(command(1, [sys.executable, '-c', 'raise SystemExit(7)']),
                           capture_output=True, text=True, timeout=5)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Expected own session', p.stderr)
        p = subprocess.run(command(1, [sys.executable, '-c', 'raise SystemExit(7)']),
                           start_new_session=True, capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 7)
        self.assertTrue(running(os.getpid()))


if __name__ == '__main__':
    unittest.main()
