"""Pure identity rejection plus a real, harmless child-lifetime test; no NARS."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import parent_guard


class ParentGuardTests(unittest.TestCase):
    def test_wrong_parent_is_rejected_without_prctl(self):
        with patch.object(parent_guard.ctypes,'CDLL',side_effect=AssertionError('must not configure')):
            for pid in (0,1,True,os.getpid()):
                with self.assertRaises(RuntimeError):parent_guard.bind_parent(pid)

    def test_failed_prctl_is_explicit(self):
        with patch.object(parent_guard.os,'getppid',return_value=123),patch.object(parent_guard.ctypes,'CDLL') as lib:
            lib.return_value.prctl.return_value=-1
            with self.assertRaises(OSError):parent_guard.bind_parent(123)

    def test_parent_race_is_rejected(self):
        with patch.object(parent_guard.os,'getppid',side_effect=[123,1]),patch.object(parent_guard.ctypes,'CDLL') as lib:
            lib.return_value.prctl.return_value=0
            with self.assertRaises(RuntimeError):parent_guard.bind_parent(123)

    def test_native_child_dies_when_its_calling_parent_is_killed(self):
        child_code=('import sys,os,time;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');'
            'from parent_guard import bind_parent;bind_parent(int(sys.argv[1]));'
            'print(os.getpid(),flush=True);time.sleep(10)')
        parent_code=('import subprocess,sys,os;'
            'p=subprocess.Popen([sys.executable,"-I","-B","-c",'+repr(child_code)+',str(os.getpid())]);p.wait()')
        parent=subprocess.Popen([sys.executable,'-I','-B','-c',parent_code],stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            # The test parent remains alive until we explicitly kill it.
            import selectors
            with selectors.DefaultSelector() as selector:
                selector.register(parent.stdout,selectors.EVENT_READ)
                self.assertTrue(selector.select(3),'child failed to become ready')
            child=int(parent.stdout.readline().strip())
            parent.kill();out,err=parent.communicate(timeout=3)
            self.assertEqual(err,'')
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                try:state=Path(f'/proc/{child}/stat').read_text().rsplit(')',1)[1].split()[0]
                except FileNotFoundError:break
                if state=='Z':break
                time.sleep(.01)
            else:self.fail('native child survived caller death')
        finally:
            if parent.poll() is None:
                os.killpg(parent.pid,signal.SIGKILL);parent.wait(timeout=3)
            parent.stdout.close();parent.stderr.close()


if __name__=='__main__':unittest.main()
