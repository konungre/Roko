import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import prepare_extended as prep

ROOT=prep.ROOT
spec=importlib.util.spec_from_file_location('prior_supervisor_tests',ROOT/'boot/granite-portable/test_supervise.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
old.HERE=prep.OUT/'roko/runtime/granite'
SupervisionTests=old.SupervisionTests

class ExtendedTests(unittest.TestCase):
    def test_exact_timeout_only_native_source_and_fixture(self):
        self.assertEqual((prep.BUILD/'granite-guest-900.cpp').read_text(),(ROOT/'boot/granite-guest/granite-guest.cpp').read_text().replace('alarm(300);','alarm(900);'))
        self.assertEqual((prep.HERE/'guest_request.py').read_bytes(),(prep.OLD/'guest_request.py').read_bytes())
        manifest=json.loads((prep.OUT/'manifest.json').read_text())
        original=json.loads((prep.original.OUT/'manifest.json').read_text())
        allowed={'adapters/runtime_select.py','adapters/granite_guest.py','runtime/granite/supervise.py','runtime/granite/generic/infer','runtime/granite/avx2/infer','granite-portable-runtime.lock.json'}
        changed={p for p in manifest['files'] if manifest['files'][p]['sha256'] != original['files'][p]['sha256']}
        self.assertEqual(changed,allowed)
        for p,row in manifest['files'].items():self.assertEqual(prep.sha((prep.OUT/'roko'/p).read_bytes()),row['sha256'])
        for p in ['adapters/granite_guest.py','adapters/runtime_select.py','runtime/granite/supervise.py']:
            compile((prep.OUT/'roko'/p).read_text(),p,'exec')
    def test_plan_bounds_and_no_model_read(self):
        spec=importlib.util.spec_from_file_location("extended_run_model",prep.HERE/"run_model.py")
        run_model=importlib.util.module_from_spec(spec);spec.loader.exec_module(run_model)
        with patch.object(run_model.host_model,'open_model',side_effect=AssertionError('model read')):
            _,plan=run_model.prepared_delta()
        self.assertEqual((plan['bounds']['native_seconds'],plan['bounds']['provider_seconds'],plan['bounds']['vm_seconds']),(900,930,1200))
        self.assertEqual(plan['bounds']['startup_seconds'],120)
        self.assertEqual(plan['bounds']['native_rss_bytes'],5*1024**3)
        self.assertEqual(plan['bounds']['guest_available_floor_bytes'],512*1024**2)
        self.assertFalse(plan['model_copy_created'])
    def test_exact_native_loader_without_model(self):
        root=ROOT/'build/granite-portable-runtime-v1/relocated-v2'
        loader=root/'system/ld-linux-x86-64.so.2'
        for name in ('avx2','generic'):
            exe=prep.BUILD/(name+'-infer')
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

if __name__=='__main__':unittest.main()
