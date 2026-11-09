"""Contract, provenance, controller and numeric-reference tests. No native MetaMo."""
import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import signal
import unittest
from unittest.mock import patch
import contract as c
from fixtures import cases
from reference_oracle import score
from paths import ROOT, HERE, IMPORTS
import gateway

class Contract(unittest.TestCase):
    def setUp(self): self.request=deepcopy(cases()[1][1])
    def test_valid_fixtures(self):
        for _,request,_ in cases(): self.assertEqual(c.parse_request(c.canonical(request)),request)
    def test_ids_never_enter_expressions(self):
        self.request['candidates'][0]['id']='text-with-period.and-hyphen'
        generated=c.canonical(c.expressions(self.request)).decode()
        self.assertNotIn('text-with-period',generated)
        self.assertNotIn(self.request['request_id'],generated)
    def test_pure_oracle_winners(self):
        for _,request,winner in cases():
            scores=[score(request['state'],a) for a in request['candidates']]
            self.assertEqual(request['candidates'][max(range(len(scores)),key=scores.__getitem__)]['id'],winner)
    def test_fixture_reset(self): self.assertEqual(cases(),cases())
    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):c.decode(b'{"a":1,"a":2}')
    def test_bad_utf8(self):
        with self.assertRaises(ValueError):c.decode(b'\xff')
    def test_empty_json(self):
        with self.assertRaises(ValueError):c.decode(b'')
    def test_oversize_json(self):
        with self.assertRaises(ValueError):c.decode(b' '*16385)
    def test_nonfinite_json(self):
        for x in ('NaN','Infinity','-Infinity'):
            with self.assertRaises(ValueError):c.decode(x.encode())
    def test_native_response_roundtrip(self):
        r=self.request;scores=[score(r['state'],a) for a in r['candidates']]
        answer=c.response_from_native(r,scores,'metamo_candidate_1',r['candidates'][1]['delta_goals'])
        self.assertEqual(c.validate_response(c.canonical(answer),r),answer)
        self.assertIs(answer['authorizes_actions'],False)
    def test_native_tie_selection_checked(self):
        r=cases()[5][1]
        with self.assertRaises(ValueError):c.response_from_native(r,[1,1],'metamo_candidate_1',[0]*8)
    def test_nonfinite_score_rejected(self):
        for v in (True,float('nan'),float('inf'),31,-31,'1'):
            with self.assertRaises(ValueError):c.response_from_native(self.request,[v,1],'metamo_candidate_1',[0]*8)
    def test_unknown_native_symbol(self):
        with self.assertRaises(ValueError):c.response_from_native(self.request,[1,2],'evil',[0]*8)
    def test_native_delta_substitution(self):
        with self.assertRaises(ValueError):c.response_from_native(self.request,[1,2],'metamo_candidate_1',[0]*8)
    def test_authority_changes_rejected(self):
        r=self.request;answer=c.response_from_native(r,[1,2],'metamo_candidate_1',r['candidates'][1]['delta_goals'])
        for key,value in [('authorizes_actions',True),('executed_actions',1),('executed_actions',False),('state_changed',True),('version',True)]:
            changed=dict(answer);changed[key]=value
            with self.assertRaises(ValueError):c.validate_response(c.canonical(changed),r)
    def test_score_order_substitution(self):
        r=self.request;answer=c.response_from_native(r,[1,2],'metamo_candidate_1',r['candidates'][1]['delta_goals'])
        answer['scores'].reverse()
        with self.assertRaises(ValueError):c.validate_response(c.canonical(answer),r)
    def test_fixture_score_golden(self):
        self.assertAlmostEqual(score(cases()[0][1]['state'],cases()[0][1]['candidates'][0]),0.31375)

def rejection(name, mutate):
    def test(self):
        mutate(self.request)
        with self.assertRaises((ValueError,TypeError)): c.parse_request(c.canonical(self.request))
    setattr(Contract,'test_reject_'+name,test)

for name,mutate in [
 ('version_bool',lambda r:r.update(version=True)),('wrong_version',lambda r:r.update(version=2)),
 ('unknown_operation',lambda r:r.update(operation='execute_action')),('extra_root_field',lambda r:r.update(command='x')),
 ('missing_state',lambda r:r.pop('state')),('bad_request_id',lambda r:r.update(request_id='!(py-call x)')),
 ('long_id',lambda r:r.update(request_id='x'*65)),('empty_id',lambda r:r.update(request_id='')),
 ('goal_shape',lambda r:r['state'].update(goals=[0]*7)),('mod_shape',lambda r:r['state'].update(modulators=[0]*7)),
 ('goal_type',lambda r:r['state'].update(goals=[True]+[0]*7)),('goal_low',lambda r:r['state'].update(goals=[-0.1]+[0]*7)),
 ('goal_high',lambda r:r['state'].update(goals=[1.1]+[0]*7)),('goal_precision',lambda r:r['state'].update(goals=[0.0000001]+[0]*7)),
 ('mod_dict',lambda r:r['state'].update(modulators={})),('empty_candidates',lambda r:r.update(candidates=[])),
 ('too_many_candidates',lambda r:r.update(candidates=r['candidates']*5)),
 ('duplicate_ids',lambda r:r['candidates'][1].update(id=r['candidates'][0]['id'])),
 ('candidate_source',lambda r:r['candidates'][0].update(code='x')),('risk_bool',lambda r:r['candidates'][0].update(risk=False)),
 ('risk_high',lambda r:r['candidates'][0].update(risk=1.1)),('risk_low',lambda r:r['candidates'][0].update(risk=-0.1)),
 ('corr_high',lambda r:r['candidates'][0].update(correlations=[1.1]*8)),('corr_low',lambda r:r['candidates'][0].update(correlations=[-1.1]*8)),
 ('delta_high',lambda r:r['candidates'][0].update(delta_goals=[0.11]*8)),('delta_low',lambda r:r['candidates'][0].update(delta_goals=[-0.11]*8)),
 ('delta_shape',lambda r:r['candidates'][0].update(delta_goals=[])),('candidate_identifier_code',lambda r:r['candidates'][0].update(id='(action x)')),
]: rejection(name,mutate)

class Provenance(unittest.TestCase):
    def test_numeric_dependencies_before_upstream_consumer(self):
        self.assertEqual(IMPORTS[0],HERE/'numeric_compat.metta')
        self.assertEqual(IMPORTS[-1],ROOT/'upstream/magus/decision.metta')
    def test_real_expression_regression_for_import_binding(self):
        from helper_probes import PROBES
        row=PROBES[-1]
        self.assertEqual(row[0],'upstream-growth-helper-binding')
        self.assertIn('!(magusNormalizedGrowthSignal (action probe',row[1])
        # Independent manual fixture: .7 * mean(.5,.3,.1) + .3 * mean(1,.5,0)
        self.assertAlmostEqual(row[2],0.7*(0.5+0.3+0.1)/3+0.3*(1+0.5+0)/3)
    def test_regression_consumer_uses_real_helper_calls(self):
        if not (ROOT/'upstream/magus/decision.metta').is_file():self.skipTest('Exact-pin upstream modules are external')
        source=(ROOT/'upstream/magus/decision.metta').read_text()
        self.assertIn('(* 0.7 (positivePart $exploratoryAlignment))',source)
        self.assertIn('(meanAtIndices (clipVector (scaleArray $deltaG 10.0) 0.0 1.0)',source)
    def test_stage_diagnostics_use_bounded_indices_not_user_text(self):
        source=(HERE/'worker.pl').read_text()
        self.assertIn('between(0,15,Index)',source)
        self.assertIn("'ROKO_METAMO_STAGE probe ~d~n'",source)
        self.assertIn("'ROKO_METAMO_STAGE score ~d~n'",source)
    def test_upstream_byte_identity(self):
        lock=json.loads((ROOT/'proof/upstream-lock.json').read_bytes())
        if any(not (ROOT/name).is_file() for name in lock['files']):self.skipTest('Exact-pin upstream review files are external')
        for name,row in lock['files'].items():
            raw=(ROOT/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),row['git_blob_sha'])
    def test_mit_notice_included(self): self.assertIn('Copyright (c) 2026 iCog Labs',(ROOT/'upstream/LICENSE').read_text())
    def test_exact_five_upstream_modules(self):
        self.assertEqual(len(IMPORTS),6)
        if any(not p.is_file() for p in IMPORTS):self.skipTest('Exact-pin upstream modules are external')
        for p in IMPORTS:
            s=p.read_text()
            for forbidden in ('!(import','py-call','py-dot','exec!','system!'):
                self.assertNotIn(forbidden,s)
    def test_bridge_has_no_oracle_or_numpy(self):
        source=(HERE/'bridge.py').read_text()
        self.assertNotIn('reference_oracle',source);self.assertNotIn('numpy',source)
    def test_authored_python_parses(self):
        for p in HERE.glob('*.py'): ast.parse(p.read_text(),filename=str(p))
    def test_helper_names_exact(self):
        s=(HERE/'numeric_compat.metta').read_text()
        for name in ('absNumber','expNum','sigmoidNum','positivePart','scaleArray','clipVector','meanAtIndices'):
            self.assertEqual(s.count('(= ('+name+' '),1)

class NumericReferences(unittest.TestCase):
    def test_installed_numpy_reference(self):
        # Existing trusted host package only. No import of upstream Python code.
        try:import numpy as np
        except ImportError:self.skipTest('Optional existing NumPy reference unavailable; no installation')
        rng=random.Random(1497)
        for _ in range(100):
            x=round(rng.uniform(-3,3),6)
            self.assertEqual(abs(x),abs(float(x)))
            self.assertAlmostEqual(math.exp(x),float(np.exp(x)),places=12)
            self.assertAlmostEqual(1/(1+math.exp(-x)),float(1/(1+np.exp(-x))),places=12)
            self.assertEqual(max(0.,x),float(np.maximum(0.,x)))
            a=[round(rng.uniform(-.1,.1),6) for _ in range(8)]
            self.assertEqual([round(v*10,8) for v in a],np.round(np.asarray(a)*10,8).tolist())
            self.assertEqual([min(1.,max(0.,v)) for v in a],np.clip(a,0.,1.).tolist())
            self.assertAlmostEqual(sum(a[j] for j in (3,4,5))/3,float(np.mean(np.asarray(a)[[3,4,5]])),places=14)
    def test_empty_mean_convention(self):
        if not (ROOT/'review-only/core/helpers.py').is_file():self.skipTest('Exact-pin upstream helper reference is external')
        self.assertIn('return float(np.mean(vals)) if vals else 0.0',(ROOT/'review-only/core/helpers.py').read_text())
        self.assertIn('(if (== $indices ()) 0.0',(HERE/'numeric_compat.metta').read_text())
    def test_rounding_half_ties_excluded_by_domain(self):
        for x in (0.000000005,0.000000015,-0.000000005):
            with self.assertRaises(ValueError):c.number(x,-.1,.1)
    def test_conflict_threshold_strict(self):
        r=cases()[0][1];a=deepcopy(r['candidates'][0]);a['correlations']=[0]*8
        a['correlations'][3]=0.5;a['correlations'][6]=-0.4
        exact=score(r['state'],a);a['correlations'][6]=-0.400002
        self.assertGreater(exact-score(r['state'],a),1.8)

class Lifecycle(unittest.TestCase):
    def test_host_four_gib_floor_before_process(self):
        import sys
        launcher=str(Path(sys.executable).resolve())
        lock={'host_launcher_python':launcher,'files':{launcher:{}}}
        with patch.object(gateway,'verify_inputs',return_value=lock),patch.object(gateway,'available',return_value=3*1024**3):
            with self.assertRaisesRegex(ValueError,'4GiB available memory reserve'):
                gateway.run_native('metamo',cases()[0][1],'a'*64,outer_deadline=gateway.time.monotonic()+10)
    def test_child_address_space_remains_separate(self):
        self.assertIn('resource.RLIMIT_AS,(512*1024**2,512*1024**2)',(HERE/'launch.py').read_text())
    def test_temporary_cleanup_retains_successful_child_receipt(self):
        class Work:
            def __enter__(self):return '/not-created'
            def __exit__(self,*args):raise OSError('mock cleanup failure')
        receipt={'status':'passed','stdout':'real-child-observation'}
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(OSError) as caught:
                with gateway.temporary_work({'receipt':receipt}):pass
        self.assertIs(caught.exception.receipt,receipt)
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['stdout'],'real-child-observation')
        self.assertEqual(receipt['temporary_cleanup'],'uncertain')
    def test_temporary_cleanup_retains_primary_cancellation(self):
        class Cancelled(BaseException):pass
        class Work:
            def __enter__(self):return '/not-created'
            def __exit__(self,*args):raise OSError('mock cleanup failure')
        receipt={'stdout':'known-prefix'};cancel=Cancelled('mock cancel');cancel.receipt=receipt
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(Cancelled) as caught:
                with gateway.temporary_work({}):raise cancel
        self.assertIs(caught.exception,cancel)
        self.assertIs(caught.exception.receipt,receipt)
        self.assertIn('Cancelled',receipt['primary_error'])
    def test_temporary_native_error_retained_when_cleanup_succeeds(self):
        class Work:
            def __enter__(self):return '/not-created'
            def __exit__(self,*args):return False
        error=ValueError('known failure')
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(ValueError) as caught:
                with gateway.temporary_work({}):raise error
        self.assertIs(caught.exception,error)
    def test_host_interpreter_mismatch_before_process(self):
        with patch.object(gateway,'verify_inputs',return_value={'host_launcher_python':'/wrong/python','files':{}}):
            with self.assertRaisesRegex(ValueError,'launcher differs'):
                gateway.run_native('metamo',cases()[0][1],'a'*64,outer_deadline=gateway.time.monotonic()+10)
    def test_deferred_cancellation(self):
        seen=[]
        def handler(n,f):seen.append(n);raise InterruptedError()
        with self.assertRaises(InterruptedError):gateway.replay_deferred_signal({signal.SIGTERM:handler},[signal.SIGTERM])
        self.assertEqual(seen,[signal.SIGTERM])
    def test_no_signal(self):gateway.replay_deferred_signal({},[])
    def test_ignored(self):gateway.replay_deferred_signal({signal.SIGTERM:signal.SIG_IGN},[signal.SIGTERM])
    def test_default(self):
        with self.assertRaises(InterruptedError):gateway.replay_deferred_signal({signal.SIGTERM:signal.SIG_DFL},[signal.SIGTERM])
    def test_first_only(self):
        seen=[];handler=lambda n,f:seen.append(n)
        gateway.replay_deferred_signal({signal.SIGTERM:handler},[signal.SIGTERM,signal.SIGTERM]);self.assertEqual(len(seen),1)
    def test_already_reaped(self):
        class P:returncode=0;pid=123
        with patch.object(gateway.os,'killpg',side_effect=AssertionError('stale signal')):
            self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'already-reaped')
    def test_lost_owner(self):
        class P:returncode=None;pid=123
        with patch.object(gateway,'observed_exit',side_effect=ChildProcessError()),patch.object(gateway.os,'killpg',side_effect=AssertionError('lost signal')):
            self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'lost')
    def test_signal_before_reap(self):
        events=[]
        class P:
            returncode=None;pid=123
            def wait(self,timeout):events.append('reap');self.returncode=0;return 0
        with patch.object(gateway,'observed_exit',side_effect=lambda p:events.append('observe')),patch.object(gateway.os,'killpg',side_effect=lambda p,s:events.append('signal')):
            self.assertTrue(gateway.stop_owned(P(),gateway.time.monotonic()+1)['reaped'])
        self.assertEqual(events,['observe','signal','reap'])

if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('Native process forbidden in pure tests')),patch('os.execve',side_effect=AssertionError('Native exec forbidden')):
        unittest.main(verbosity=2)
