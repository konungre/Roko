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
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_fourcore as r


def running(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()[0] != 'Z'
    except FileNotFoundError:
        return False


class RecoveryTests(unittest.TestCase):
    def test_exact_threading_only_candidate_and_plan(self):
        r.prepare_fourcore.validate()
        _, plan = r.base.prepared_delta()
        prior = json.loads((r.ROOT / 'build/granite-model-guest/attempt-2/assembly.json').read_text())
        for key in ('request', 'expected', 'root_sha256', 'input_token_cap', 'output_token_cap'):
            self.assertEqual(plan[key], prior[key])
        bounds = dict(prior['bounds'], tcg_cpus=4, native_threads=4)
        self.assertEqual(plan['bounds'], bounds)
        with tempfile.TemporaryDirectory() as temp:
            _, assembly = r.base.assemble(Path(temp))
            self.assertEqual(assembly['bounds'], bounds)
            self.assertNotEqual(assembly['initramfs_sha256'], prior['initramfs_sha256'])
        assets={'qemu':{'path':'qemu'},'kernel':{'path':'kernel'}}
        with patch.object(r.base.root_image,'attach',return_value=[]), patch.object(r.base.host_model,'attachment',return_value=[]):
            args=r.base.command(assets,Path('test-bootstrap'),1,2,{})
        self.assertEqual(args[args.index('-smp')+1],'4')
        self.assertEqual(args[args.index('-accel')+1],'tcg,thread=multi')
        self.assertEqual(args[args.index('-m')+1],'6144')
        self.assertEqual(args[args.index('-nic')+1],'none')

    def test_exact_native_loader_without_model(self):
        root=r.ROOT/'build/granite-portable-runtime-v1/relocated-v2'
        loader=root/'system/ld-linux-x86-64.so.2'
        for name in ('avx2','generic'):
            exe=r.prepare_fourcore.BUILD/(name+'-infer')
            command=[str(loader),'--inhibit-cache','--glibc-hwcaps-mask','','--library-path',str(root/'avx2/lib')+':'+str(root/'system')]
            result=subprocess.run(command+['--list',str(exe)],capture_output=True,text=True,timeout=3,check=True)
            paths=[]
            for line in result.stdout.splitlines():
                if '=>' in line:paths.append(line.split('=>',1)[1].split()[0])
                elif line.strip().startswith('/'):paths.append(line.strip().split()[0])
            self.assertTrue(paths)
            self.assertTrue(all(Path(p).is_relative_to(root) for p in paths),result.stdout)
            result=subprocess.run(command+[str(exe)],capture_output=True,text=True,timeout=3)
            self.assertEqual(result.returncode,2)
            self.assertIn('expected --model PATH',result.stderr)

    def test_atomic_receipt_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'receipt.json'
            r.atomic_json(target, {'state': 'running'})
            r.atomic_json(target, {'state': 'complete'})
            self.assertEqual(json.loads(target.read_text()), {'state': 'complete'})
            self.assertFalse(target.with_name(target.name + '.tmp').exists())

    def test_guard_refuses_wrong_parent(self):
        p = subprocess.run([sys.executable, '-c', 'import time; time.sleep(30)'],
                           preexec_fn=lambda: r.child_guard(-1), timeout=3)
        self.assertEqual(p.returncode, 125)

    def test_parent_death_kills_child(self):
        with tempfile.TemporaryDirectory() as temp:
            pidfile = Path(temp) / 'child.pid'
            body = '''import os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import run_fourcore as r
parent=os.getpid()
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True,preexec_fn=lambda:r.child_guard(parent))
Path(sys.argv[2]).write_text(str(p.pid));time.sleep(30)
'''
            parent = subprocess.Popen([sys.executable, '-c', body, str(HERE), str(pidfile)], start_new_session=True)
            try:
                deadline = time.monotonic() + 3
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(pidfile.exists())
                pid = int(pidfile.read_text())
                self.assertTrue(running(pid))
                parent.kill()
                parent.wait(timeout=2)
                deadline = time.monotonic() + 2
                while running(pid) and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertFalse(running(pid))
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait(timeout=2)

    def test_signal_handler_and_group_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt = Path(temp) / 'receipt.json'
            body = '''import json,os,signal,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import run_fourcore as r
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
signal.signal(signal.SIGTERM,r.cancelled)
r.atomic_json(Path(sys.argv[2]),{'state':'running','pid':p.pid})
try:time.sleep(30)
except InterruptedError:pass
finally:
 r.base.terminate(p)
 r.atomic_json(Path(sys.argv[2]),{'state':'cleaned','returncode':p.returncode,'pid':p.pid})
'''
            parent = subprocess.Popen([sys.executable, '-c', body, str(HERE), str(receipt)], start_new_session=True)
            try:
                deadline = time.monotonic() + 3
                while not receipt.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(receipt.exists())
                parent.terminate()
                parent.wait(timeout=3)
                final = json.loads(receipt.read_text())
                self.assertEqual(final['state'], 'cleaned')
                self.assertFalse(running(final['pid']))
                self.assertEqual(final['returncode'], -signal.SIGTERM)
            finally:
                if parent.poll() is None:
                    parent.kill(); parent.wait(timeout=2)

    def test_resource_refusal_before_attempt_or_model_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'results').mkdir(); (root / 'build').mkdir()
            with patch.object(r, 'ROOT', root), patch.object(r.base, 'available', return_value=0), patch.object(r.base.host_model, 'open_model', side_effect=AssertionError('must not open model')):
                result = r.run()
            self.assertFalse(result['boot_tested'])
            self.assertTrue(result['errors'])
            self.assertEqual(list((root / 'build/granite-model-guest').iterdir()), [])
            self.assertEqual([p.name for p in (root / 'results/granite-model-guest').iterdir()], ['recovery-lane.lock'])

if __name__ == '__main__': unittest.main()
