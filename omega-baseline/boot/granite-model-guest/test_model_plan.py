import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import host_model
import memory_guard
import prepare


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


old=module('guarded_cancellation_tests',ROOT/'boot/granite-portable/test_supervise.py')
old.HERE=prepare.OUT/'roko/runtime/granite'
SupervisionTests=old.SupervisionTests


class ModelPlanTests(unittest.TestCase):
    def test_synthetic_receipt_verified_and_native_stage_exact(self):
        proof=prepare.synthetic_proof()
        self.assertTrue(proof['passed'])
        manifest=json.loads((prepare.OUT/'manifest.json').read_text())
        self.assertLess(manifest['payload_bytes'],20*1024**2)
        self.assertFalse(manifest['model_read'])
        for name,row in manifest['files'].items():
            data=(prepare.OUT/'roko'/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
        for mode in ('generic','avx2'):
            self.assertEqual((prepare.OUT/f'roko/runtime/granite/{mode}/infer').read_bytes(),
                             (ROOT/f'build/granite-portable-runtime-v1/relocated-v2/{mode}/infer').read_bytes())

    def test_candidate_remains_disabled(self):
        base=prepare.OUT/'roko'
        runtime=json.loads((base/'granite-portable-runtime.lock.json').read_text())
        raw=json.loads((base/'granite-raw-transport.lock.json').read_text())
        self.assertEqual(runtime['status'],'candidate-only-awaiting-execution-grant')
        self.assertFalse(runtime['optimized_loader_admitted'])
        self.assertFalse(raw['reviewed_admission'])
        self.assertEqual(raw['synthetic_receipt_sha256'],prepare.RECEIPT_SHA)

    def test_guard_thresholds_are_finite_and_fail_closed(self):
        normal={'aggregate_rss_bytes':memory_guard.RSS_LIMIT,'guest_available_bytes':memory_guard.AVAILABLE_FLOOR}
        self.assertIsNone(memory_guard.reason(normal))
        self.assertEqual(memory_guard.reason(dict(normal,aggregate_rss_bytes=memory_guard.RSS_LIMIT+1)),'native-tree-rss-cap')
        self.assertEqual(memory_guard.reason(dict(normal,guest_available_bytes=memory_guard.AVAILABLE_FLOOR-1)),'guest-available-reserve')

    def test_small_rss_guard_fixture_kills_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original=(prepare.OUT/'roko/runtime/granite/supervise.py').read_text()
            (root/'supervise.py').write_text(original)
            guard=(HERE/'memory_guard.py').read_text().replace('RSS_LIMIT = 5 * 1024**3','RSS_LIMIT = 1')
            (root/'memory_guard.py').write_text(guard)
            args=[sys.executable,str(root/'supervise.py'),'--parent-pid',str(os.getpid()),
                  '--parent-start',str(old.supervise.process(os.getpid())['start']),
                  '--seconds','2','--',sys.executable,'-c','import time;time.sleep(10)']
            result=subprocess.run(args,start_new_session=True,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,137,result.stderr)
            self.assertIn('native-tree-rss-cap',result.stderr)
            self.assertIn('descendants_cleaned=1',result.stderr)
            self.assertIn('ROKO_SUPERVISOR_USAGE',result.stderr)

    def test_host_model_rejects_wrong_regular_file_without_hashing(self):
        with tempfile.TemporaryFile() as stream, patch.object(host_model.os,'pread',side_effect=AssertionError('unexpected read')):
            with self.assertRaisesRegex(ValueError,'exact locked'):
                host_model.verify(stream.fileno())

    def test_prepared_delta_is_disabled_and_has_no_model_bytes(self):
        import run_model
        with patch.object(host_model,'open_model',side_effect=AssertionError('model read')):
            entries,plan=run_model.prepared_delta()
        self.assertFalse(plan['model_included'])
        self.assertLess(plan['payload_bytes'],20*1024**2)
        self.assertEqual(plan['bounds']['sampler_sleep_seconds'],0.1)
        runtime=json.loads(entries['granite-model-probe/roko/granite-portable-runtime.lock.json'][0])
        self.assertEqual(runtime['status'],'candidate-only-awaiting-execution-grant')
        subprocess.run(['sh','-n'],input=entries['init'][0],check=True,timeout=3)
        subprocess.run(['sh','-n'],input=entries['granite-model-probe/init'][0],check=True,timeout=3)

    def test_actual_controller_checks_integer_and_never_dispatches(self):
        state_module=module('probe_working_state',ROOT/'adapters/working_state.py')
        for answer,accepted in [('56',True),('7 * 8',False),('55',False)]:
            state=state_module.WorkingState('inert','arithmetic')
            state.add_evidence('input','fixture','Arithmetic: 7 * 8.')
            state.propose('inert','record_answer',{'text':answer},['input'])
            self.assertEqual(state.verify_arithmetic()['accepted'],accepted)
            self.assertEqual(state.snapshot()['executed_actions'],0)
            self.assertNotEqual(state.snapshot()['phase'],'closed')


if __name__=='__main__':unittest.main()
