"""Real current avatar bridge plus staged provider, with explicitly inert stand-ins."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STAGE=ROOT/'build-src/granite-portable-stage/source-v2/opt/roko'
inputs=json.loads((ROOT/'boot/roko-corner-guest/inputs.json').read_text())
bridge_path=Path(inputs['stage'])/'usr/share/roko/corner/task_bridge.py'
expected=next(x['sha256'] for x in inputs['files'] if x['path'].endswith('/task_bridge.py'))
assert hashlib.sha256(bridge_path.read_bytes()).hexdigest()==expected
spec=importlib.util.spec_from_file_location('actual_avatar_task_bridge',bridge_path)
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
spec=importlib.util.spec_from_file_location('cleanup_probe',HERE/'supervise.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

PARENT=r'''
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'adapters'),str(root/'vendor/guest-python'),str(root/'vendor/PeTTa/repos/Omega/src')]
import providers,granite_guest
# Test-only native stand-in. No admitted start, weights or model inference.
p=granite_guest.GraniteGuestProvider(root);p.ready=True;p.model=Path('/not-a-model')
body='import subprocess,sys,time,os,json; from pathlib import Path; c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True); Path(sys.argv[1]).write_text(json.dumps([os.getpid(),c.pid])); time.sleep(30)'
p.command_prefix=[sys.executable,'-c',body,sys.argv[2]]
t=providers.LLMTool().with_name('record_answer').with_description('inert').add_parameter(providers.LLMToolParameter().with_name('text'))
r=providers.LLMRequest().with_messages([providers.llmRequestMessage('user','inert')]).with_max_tokens(64).with_tools([t])
p.chat(r)
'''


class BridgeCleanupTests(unittest.TestCase):
    def check(self,cancel):
        with tempfile.TemporaryDirectory() as tmp:
            pids=Path(tmp)/'pids.json';event=threading.Event()
            def trigger():
                end=time.monotonic()+3
                while not pids.exists() and time.monotonic()<end:time.sleep(.01)
                event.set()
            thread=threading.Thread(target=trigger) if cancel else None
            if thread:thread.start()
            try:
                with self.assertRaises(bridge.BridgeError):
                    bridge._run([sys.executable,'-c',PARENT,str(STAGE),str(pids)],.7 if not cancel else 4,event if cancel else None)
            finally:
                if thread:thread.join(timeout=4)
            self.assertTrue(pids.exists(),'The native stand-in must actually start')
            ids=json.loads(pids.read_text())
            def alive(pid):
                row=probe.process(pid);return bool(row and row['state']!='Z')
            end=time.monotonic()+2
            while any(alive(pid) for pid in ids) and time.monotonic()<end:time.sleep(.02)
            self.assertTrue(all(not alive(pid) for pid in ids),ids)
            self.assertTrue(alive(os.getpid()),'Caller process must survive')
    def test_real_bridge_cancel_reaps_provider_helper_and_detached_child(self):self.check(True)
    def test_real_bridge_timeout_reaps_provider_helper_and_detached_child(self):self.check(False)


if __name__=='__main__':unittest.main()
