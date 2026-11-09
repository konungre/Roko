"""Fresh profile admission and real Linux supervisor lifecycle checks."""
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import conversation
import fresh
import fresh_supervise


class FreshAdmissionTests(unittest.TestCase):
    def test_modified_native_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            native = Path(temp)/'infer'
            native.write_bytes(b'original')
            expected = hashlib.sha256(native.read_bytes()).hexdigest()
            profile = Path(temp)/'profile.json'
            profile.write_text(json.dumps({'kind':'roko-fresh-host-v1', 'files':{str(native):expected}}))
            native.write_bytes(b'modified')
            with self.assertRaisesRegex(ValueError, 'closure mismatch'):
                fresh.load_profile(profile)

    def test_relative_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)/'profile.json'
            profile.write_text(json.dumps({'kind':'roko-fresh-host-v1', 'files':{'infer':'arbitrary'}}))
            with self.assertRaisesRegex(ValueError, 'closure mismatch'):
                fresh.load_profile(profile)

    def test_missing_executable_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)/'profile.json'
            profile.write_text(json.dumps({'kind':'roko-fresh-host-v1',
                'model':'/model', 'infer':'/infer', 'swipl':'/swipl', 'python':'/python',
                'files':{'/model':fresh.recovered.MODEL_SHA}}))
            with patch.object(fresh, 'digest', return_value=fresh.recovered.MODEL_SHA):
                with self.assertRaisesRegex(ValueError, 'Unpinned executable.*infer'):
                    fresh.load_profile(profile)

    def test_inference_refuses_network_enabled_process(self):
        with self.assertRaisesRegex(ValueError, 'network denial'):
            fresh.FreshProvider({})

    def test_unqualified_context_preserves_committed_history(self):
        session = conversation.Session(None, fresh.no_context)
        session.history = [{'role':'user', 'content':'earlier'},
                           {'role':'assistant', 'content':'reply'}]
        original = list(session.history)
        with self.assertRaisesRegex(ValueError, 'ECAN is not qualified'):
            session.prepare({'text':'next', 'context':[
                {'id':'fact','text':'hello','sti':1,'lti':1,'stimulus':1}]})
        self.assertEqual(session.history, original)
        self.assertIsNone(session.pending)


@unittest.skipUnless(sys.platform == 'linux', 'Linux process identities and subreaper required')
class FreshSupervisorTests(unittest.TestCase):
    def test_worker_dies_when_launcher_is_killed(self):
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp)/'ready'
            launcher_code = (
                'import os,subprocess,sys,time; from pathlib import Path; '
                'stamp=Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(")",1)[1].split()[19]; '
                'p=subprocess.Popen([sys.executable,"-B",sys.argv[1],str(os.getpid()),stamp,'
                'sys.executable,"-c","import os,sys,time; from pathlib import Path; '
                'Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)",sys.argv[2]]); '
                'time.sleep(30)'
            )
            launcher = subprocess.Popen([sys.executable, '-c', launcher_code,
                                         str(SOURCE/'fresh_exec.py'), str(ready)])
            worker = None
            try:
                deadline = time.monotonic()+3
                while not ready.exists() and launcher.poll() is None and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists())
                worker = int(ready.read_text())
                launcher.kill()
                launcher.wait(timeout=2)
                deadline = time.monotonic()+2
                while time.monotonic()<deadline:
                    row = fresh_supervise.process(worker)
                    if row is None or row['state']=='Z':
                        break
                    time.sleep(.01)
                self.assertTrue(row is None or row['state']=='Z', row)
            finally:
                if launcher.poll() is None:
                    launcher.kill()
                    launcher.wait()
                if worker:
                    row = fresh_supervise.process(worker)
                    if row and row['state']!='Z':
                        os.kill(worker, signal.SIGKILL)

    def run_case(self, cancel):
        with tempfile.TemporaryDirectory() as temp:
            pidfile = Path(temp)/'child.pid'
            # A child which escapes the process group must still be adopted and
            # killed by the subreaper. Nothing here loads a model or uses network.
            native_code = (
                'import subprocess,sys,time; '
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"], '
                'start_new_session=True); '
                'open(sys.argv[1],"w").write(str(p.pid)); time.sleep(30)'
            )
            stamp = fresh_supervise.process(os.getpid())['start']
            command = [sys.executable, '-B', str(SOURCE/'fresh_supervise.py'),
                       '--parent-pid', str(os.getpid()), '--parent-start', str(stamp),
                       '--seconds', '5' if cancel else '.7', '--', sys.executable,
                       '-c', native_code, str(pidfile)]
            proc = subprocess.Popen(command, start_new_session=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            child_pid = None
            try:
                deadline = time.monotonic()+3
                while not pidfile.exists() and proc.poll() is None and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue(pidfile.exists(), 'Native child did not start')
                child_pid = int(pidfile.read_text())
                if cancel:
                    proc.terminate()
                out, err = proc.communicate(timeout=5)
                self.assertEqual(out, '')
                self.assertEqual(proc.returncode, 125 if cancel else 124, err)
                self.assertIn('descendants_cleaned=1', err)
                self.assertIn('caller-cancelled-or-exited' if cancel else 'native-deadline', err)
                row = fresh_supervise.process(child_pid)
                self.assertTrue(row is None or row['state']=='Z', row)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                if child_pid is not None:
                    row = fresh_supervise.process(child_pid)
                    if row and row['state']!='Z':
                        os.kill(child_pid, signal.SIGKILL)

    def test_deadline_cleans_detached_descendant(self):
        self.run_case(False)

    def test_cancellation_cleans_detached_descendant(self):
        self.run_case(True)


SWIPL = os.environ.get('ROKO_TEST_SWIPL') or shutil.which('swipl')


@unittest.skipUnless(SWIPL, 'Set ROKO_TEST_SWIPL to test the actual Prolog bounded reader')
class RequestReaderTests(unittest.TestCase):
    def probe(self, text):
        goal = ('catch((read_request_line(user_input,A), '
                '((A==end_of_file)->writeln(eof);string_length(A,N),writeln(N))),'
                'error(resource_error(request_length),_), (writeln(oversize),halt(2))),halt.')
        return subprocess.run([SWIPL, '-q', '-f', 'none', '-l', str(SOURCE/'worker.pl'),
                               '-g', goal], input=text, capture_output=True, text=True, timeout=5)

    def test_exact_limit_and_eof(self):
        result = self.probe('x'*20000+'\n')
        self.assertEqual((result.returncode,result.stdout),(0,'20000\n'), result.stderr)
        result = self.probe('')
        self.assertEqual((result.returncode,result.stdout),(0,'eof\n'),result.stderr)

    def test_oversize_stops_before_second_line(self):
        result = self.probe('x'*20001+'\n{"text":"suffix","context":[]}\n')
        self.assertEqual((result.returncode,result.stdout),(2,'oversize\n'),result.stderr)


if __name__ == '__main__':
    unittest.main()
