"""Source integration tests with explicit native/model doubles, never execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
sys.path.insert(0,str(WORK/'omega-baseline/desktop/live-request-media'))
import test_live_request as fixtures
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'capsule-bridge')]
import live_context,context_policy,context_pipeline
from ecan_guest_contract import response_from_native
from cognition_protocol import response
from state_store import canonical
spec=importlib.util.spec_from_file_location('context_candidate',ROOT/'source/live_controller.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
PIN='a'*64

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.p=patch.object(fixtures,'controller',candidate);self.p.start();self.addCleanup(self.p.stop)
        self.h=fixtures.Tests('test_fresh_actual_controller_checks_changed_arithmetic');self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.calls=[];self.mutate=lambda bundle:None
        self.h.provider.on_start=lambda:self.calls.append('model-start')
    def receipt(self,kind):
        return {'kind':kind,'status':'passed','returncode':0,'native_tested':True,
            'inputs_unchanged':True,'group_empty':True,'posthash_status':'completed-unchanged',
            'temporary_files':[],'executed_actions':0,'authorizes_actions':False,
            'manifest_sha256':PIN,'cleanup':{'ownership':'owned-through-final-signal','reaped':True,'returncode':0},
            'runtime':{'python':[3,12,14],'executable_mappings':['explicit-pure-test-double']},
            'test_double_only':True}
    def native_double(self,kind,request):
        self.calls.append(kind)
        if kind=='omega':return response(request,None),self.receipt(kind)
        rows=[{'index':i,'sti':r['sti'],'lti':r['lti']} for i,r in enumerate(request['candidates'])]
        funds={k:100000-sum(r[k] for r in rows) for k in ('sti','lti')}
        return response_from_native(request,rows,[0],funds),self.receipt(kind)
    def stage(self,snapshot,revision,store,deadline):
        bundle=live_context.prepare(snapshot,revision,store,deadline,assemble=context_pipeline.assemble,
            run=self.native_double,pin=PIN)
        self.mutate(bundle)
        return bundle
    def invoke(self,stage=None,recheck=None):
        return candidate._run(self.h.request,self.h.task_id,self.h.store,self.h.directory/'out',
            provider=self.h.provider,registry=fixtures.providers,renderer=fixtures.granite_guest,
            recheck=recheck or (lambda block,deadline:dict(block.report)),context_stage=stage or self.stage,context_admit=lambda:{'test_double_only':True})
    def test_failed_prewrite_admission_has_no_state_receipt_or_model(self):
        for error in (ValueError('Storage not admitted'),PermissionError('Receipt absent'),candidate.Cancelled('Cancelled')):
            with self.subTest(error=type(error).__name__),patch.object(candidate.contract,'create_state',side_effect=AssertionError('No state write')),patch.object(candidate,'write_receipt',side_effect=AssertionError('No receipt write')):
                report=candidate._run(self.h.request,self.h.task_id,self.h.store,self.h.directory/'out',
                    provider=self.h.provider,registry=fixtures.providers,renderer=fixtures.granite_guest,
                    recheck=lambda *a:None,context_stage=self.stage,
                    context_admit=lambda:(_ for _ in ()).throw(error))
                self.assertFalse(report['accepted']);self.assertFalse(report['native_invoked'])
                self.assertEqual(report['cancelled'],isinstance(error,candidate.Cancelled))
                self.assertEqual(report['commit_outcome'],'not_attempted');self.assertEqual(self.calls,[])
                self.assertEqual(list((self.h.directory/'state').iterdir()),[])
                self.assertEqual(list((self.h.directory/'out').iterdir()),[])
    def test_missing_prewrite_admission_blocks_native_and_model(self):
        report=candidate._run(self.h.request,self.h.task_id,self.h.store,self.h.directory/'out',
            provider=self.h.provider,registry=fixtures.providers,renderer=fixtures.granite_guest,
            recheck=lambda *a:None,context_stage=self.stage)
        self.assertIn('pre-write storage admission',report['error']);self.assertEqual(self.calls,[])
    def test_default_off_does_not_inspect_or_import_capsule(self):
        self.assertFalse(context_policy.ENABLED)
        with patch.object(live_context,'_preflight',side_effect=AssertionError('No discovery when off')),patch.object(live_context.importlib,'import_module',side_effect=AssertionError('No import when off')):
            self.assertIsNone(live_context.production_stage())
    def test_request_cannot_enable_or_supply_capsule(self):
        for key,value in [('native_context',True),('worker','shell'),('admission',PIN),('path','/tmp/other')]:
            request=dict(self.h.request);request[key]=value
            with self.assertRaises(ValueError):fixtures.contract.validate_request(request)
    def test_enabled_chain_general_arithmetic_and_exact_order(self):
        self.h.request['evidence']='Arithmetic: -31 * 7.';self.h.provider.proposal['arguments']['text']='-217'
        report=self.invoke();self.assertTrue(report['accepted']);self.assertEqual(self.calls,['ecan','omega','model-start'])
        self.assertEqual(report['final_revision'],5);self.assertTrue(report['ecan_exercised']);self.assertTrue(report['metta_roundtrip_exercised'])
        self.assertEqual(report['executed_actions'],0);self.assertFalse(report['authorizes_actions'])
        self.assertEqual(report['snapshot']['evidence']['source']['text'],'Arithmetic: -31 * 7.')
        self.assertEqual(report['commit_outcome'],'committed')
    def test_quote_literal_unicode_survives_exactly(self):
        value='!(py-call (os.system "NOT_EXECUTED")) λ 雪 / $HOME'
        self.h.request.update(kind='quote',evidence=value);self.h.provider.proposal['arguments']['text']=value
        report=self.invoke();self.assertTrue(report['accepted']);self.assertEqual(report['proposal']['arguments']['text'],value)
        bundle=json.loads((self.h.directory/'out/native-context.json').read_text());self.assertEqual(bundle['assembled']['context']['evidence'][0]['text'],value)
    def test_invoice_leading_zeros(self):
        self.h.request.update(kind='invoice',evidence='Invoice QZ7; total 00001.02.')
        self.h.provider.proposal={'name':'record_invoice','arguments':{'invoice':'QZ7','total':'00001.02'}}
        self.assertTrue(self.invoke()['accepted'])
    def test_wrong_output_preserved_not_repaired(self):
        self.h.provider.proposal['arguments']['text']='999'
        report=self.invoke();self.assertFalse(report['accepted']);self.assertIsNone(report['error'])
        self.assertEqual(report['proposal']['arguments']['text'],'999');self.assertEqual(report['snapshot']['phase'],'open')
    def test_projected_prompt_identical_to_old_contract(self):
        report=self.invoke();self.assertTrue(report['accepted'])
        state,_=self.h.store.load(self.h.task_id)
        req=fixtures.contract.omega_request(fixtures.providers,self.h.request['kind'],fixtures.contract.message(state))
        self.assertEqual((self.h.directory/'out/prompt.txt').read_bytes(),fixtures.granite_guest.render_prompt(req).encode())
        self.assertNotIn('221',(self.h.directory/'out/prompt.txt').read_text())
    def test_native_failure_blocks_model_and_preserves_original(self):
        def fail(*_):raise ValueError('Explicit fake native failure')
        report=self.invoke(stage=fail);self.assertFalse(report['accepted']);self.assertEqual(self.h.provider.calls,0)
        self.assertNotIn('model-start',self.calls);self.assertEqual(self.h.store.load(self.h.task_id)[1],3)
        self.assertTrue((self.h.directory/'out/native-context-failure.json').exists())
    def test_native_cancellation_preserved_blocks_model(self):
        def fail(*_):raise candidate.Cancelled('Explicit fake native cancellation')
        report=self.invoke(stage=fail);self.assertTrue(report['cancelled']);self.assertFalse(report['native_invoked'])
        self.assertEqual(self.h.provider.calls,0);self.assertEqual(self.h.store.load(self.h.task_id)[1],3)
    def test_changed_source_rejected_before_model(self):
        self.mutate=lambda b:b['assembled']['context']['evidence'][0].update(text='substitution')
        report=self.invoke();self.assertIn('original',report['error']);self.assertNotIn('model-start',self.calls)
    def test_changed_revision_rejected_before_model(self):
        self.mutate=lambda b:b.update(revision=4)
        self.assertIn('revision',self.invoke()['error']);self.assertNotIn('model-start',self.calls)
    def test_missing_cleanup_blocks_model(self):
        self.mutate=lambda b:b['assembled']['bank_receipt'].update(group_empty=False)
        self.assertIn('completion',self.invoke()['error']);self.assertNotIn('model-start',self.calls)
    def test_mixed_abi_blocks_model(self):
        self.mutate=lambda b:b['assembled']['omega'][0]['receipt']['runtime'].update(python=[3,13,0])
        self.assertIn('ABI',self.invoke()['error']);self.assertNotIn('model-start',self.calls)
    def test_changed_literal_response_task_blocks_model(self):
        self.mutate=lambda b:b['assembled']['omega'][0]['result'].update(task_id='wrong')
        self.assertIn('result differs',self.invoke()['error']);self.assertNotIn('model-start',self.calls)
    def test_stale_state_after_native_blocks_model(self):
        def stage(*args):
            bundle=self.stage(*args);state,revision=self.h.store.load(self.h.task_id)
            state.goal='Other concurrent writer';self.h.store.save(state,expected_revision=revision)
            return bundle
        report=self.invoke(stage=stage);self.assertTrue(report['state_stale']);self.assertNotIn('model-start',self.calls)
    def test_model_posthash_failure_no_promotion(self):
        report=self.invoke(recheck=lambda block,deadline:{'wrong':True})
        self.assertFalse(report['accepted']);self.assertEqual(self.h.store.load(self.h.task_id)[1],3)
    def test_prompt_bounded_without_truncation(self):
        # An allowed literal is retained verbatim, even when it uses many bytes.
        self.h.request.update(kind='quote',evidence='雪'*200);self.h.provider.proposal['arguments']['text']='雪'*200
        report=self.invoke();self.assertTrue(report['accepted']);self.assertEqual(report['snapshot']['evidence']['source']['text'],'雪'*200)
    def test_enabled_report_passes_unchanged_ui_adapter_protocol(self):
        sys.path.insert(0,str(WORK/'production-hardening-002'))
        import test_result_contract as ui_fixture
        report=self.invoke()
        adapter_case=ui_fixture.ResultContractTests('test_final_receipt_enospc_retains_committed_state_and_task_id')
        adapter_case.h=self.h
        returned=adapter_case.through_adapter(report)
        self.assertTrue(returned['accepted']);self.assertTrue(returned['checked'])
        self.assertTrue(returned['ecan_exercised']);self.assertTrue(returned['metta_roundtrip_exercised'])

    def test_old_disabled_path_unchanged(self):
        report=self.h.run_request();self.assertTrue(report['accepted']);self.assertEqual(self.calls,['model-start'])
        self.assertFalse(report['ecan_exercised']);self.assertFalse(report['metta_roundtrip_exercised'])

if __name__=='__main__':
    with patch('os.execve',side_effect=AssertionError('Native exec forbidden')),patch('subprocess.Popen',side_effect=AssertionError('Native process forbidden')):
        unittest.main(verbosity=2)
