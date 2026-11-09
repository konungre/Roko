"""Authored contracts/lifecycle/trace/log checks only; no AIRIS execution."""
import ast
import copy
import json
import os
from pathlib import Path
import signal
import tempfile
import types
import unittest
from unittest.mock import patch
import contract as c
import gateway
import experiment
import worker
from run_gate import fixture

class Contract(unittest.TestCase):
 def setUp(self):self.r=fixture('pure',1,7)
 def native(self):return {'predictions':c.expected(self.r),'learned_rules':2,'rule_updates':2,'steps':4,'knowledge_snapshot_sha256':'1'*64,'max_graph_nodes':8,'max_knowledge_keys':24,'upstream_line_events':3000,'planner_calls':0}
 def packet(self):
  n=self.native();return {'version':1,'request':self.r,'native':n,'response':c.response(self.r,n),'runtime':{},'network_denial_observed':True,'upstream_sha256':'2'*64}
 def mutate(self,i,k,v):
  r=self.r['training'][i];r[k]=v;r['sha256']=c.digest({k:v for k,v in r.items() if k!='sha256'})
 def bad(self):
  with self.assertRaises(ValueError):c.validate_request(self.r)
 def test_roundtrip(self):self.assertEqual(c.parse_request(c.canonical(self.r)),self.r)
 def test_detached(self):self.assertIsNot(c.validate_request(self.r),self.r)
 def test_known_increment(self):self.assertEqual(c.expected(self.r),{'learned':{'step':8,'hold':7},'empty':{'step':7,'hold':7},'restored':{'step':8,'hold':7}})
 def test_known_decrement(self):self.assertEqual(c.expected(fixture('decrement',-1,7))['learned'],{'step':6,'hold':7})
 def test_known_double_step(self):self.assertEqual(c.expected(fixture('double',2,11))['learned'],{'step':13,'hold':11})
 def test_actual_response(self):self.assertEqual(c.validate_packet(self.packet(),self.r),c.response(self.r,self.native()))
 def test_unicode_provenance(self):self.assertIn('λ',c.response(self.r,self.native())['training'][0]['source'])
 def test_no_action_authority(self):
  r=c.response(self.r,self.native());self.assertFalse(r['authorizes_actions']);self.assertFalse(r['full_airis']);self.assertFalse(r['general_causal_learning_established']);self.assertFalse(r['persistent_state_changed'])
 def test_duplicate_json(self):
  with self.assertRaises(ValueError):c.parse_request(b'{"version":1,"version":1}')
 def test_nonfinite_json(self):
  with self.assertRaises(ValueError):c.decode(b'{"x":NaN}',100)
 def test_invalid_utf8(self):
  with self.assertRaises(ValueError):c.decode(b'\xff',10)
 def test_request_cap(self):
  with self.assertRaises(ValueError):c.parse_request(b' '*(c.MAX_REQUEST+1))
 def test_unknown_key(self):self.r['code']='exec';self.bad()
 def test_boolean_revision(self):self.r['revision']=True;self.bad()
 def test_invalid_version(self):self.r['version']=True;self.bad()
 def test_zero_revision(self):self.r['revision']=0;self.bad()
 def test_bad_identifier(self):self.r['task_id']='../escape';self.bad()
 def test_boolean_query(self):self.r['query']=True;self.bad()
 def test_float_query(self):self.r['query']=7.0;self.bad()
 def test_seen_query(self):self.r['query']=2;self.bad()
 def test_query_range(self):self.r['query']=65;self.bad()
 def test_extra_observation(self):self.r['training'].append(self.r['training'][0]);self.bad()
 def test_missing_observation(self):self.r['training'].pop();self.bad()
 def test_evidence_reuse(self):self.mutate(1,'id','evidence_0');self.bad()
 def test_bad_digest(self):self.r['training'][0]['sha256']='0'*64;self.bad()
 def test_source_cap(self):self.mutate(0,'source','x'*257);self.bad()
 def test_unknown_action(self):self.mutate(0,'action','shell');self.bad()
 def test_boolean_observation(self):self.mutate(0,'before',True);self.bad()
 def test_float_observation(self):self.mutate(0,'after',3.0);self.bad()
 def test_order_change(self):self.r['training'].reverse();self.bad()
 def test_broken_pair(self):self.mutate(2,'before',3);self.bad()
 def test_nonconstant_delta(self):self.mutate(1,'after',6);self.bad()
 def test_changed_control(self):self.mutate(2,'after',3);self.bad()
 def test_zero_step(self):self.mutate(0,'after',2);self.bad()
 def test_bad_native_numeric(self):
  for v in (True,8.0,'8',float('nan')):
   n=self.native();n['predictions']['learned']['step']=v
   with self.assertRaises(ValueError):c.response(self.r,n)
 def test_wrong_native_output(self):
  n=self.native();n['predictions']['learned']['step']=9
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_missing_ablation(self):
  n=self.native();del n['predictions']['empty']
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_missing_rules(self):
  n=self.native();n['learned_rules']=0
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_planner_forbidden(self):
  n=self.native();n['planner_calls']=1
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_graph_limit(self):
  n=self.native();n['max_graph_nodes']=25
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_knowledge_limit(self):
  n=self.native();n['max_knowledge_keys']=129
  with self.assertRaises(ValueError):c.response(self.r,n)
 def test_stale_packet(self):
  p=self.packet();r=copy.deepcopy(self.r);r['revision']=2
  with self.assertRaises(ValueError):c.validate_packet(p,r)
 def test_changed_authority(self):
  p=self.packet();p['response']['authorizes_actions']=True
  with self.assertRaises(ValueError):c.validate_packet(p,self.r)
 def test_network_required(self):
  p=self.packet();p['network_denial_observed']=False
  with self.assertRaises(ValueError):c.validate_packet(p,self.r)
 def test_parent_packet_cap(self):
  with self.assertRaises(ValueError):gateway.validate_completed('airis',b' '*(c.MAX_RESPONSE+1),b'ROKO_AIRIS_OUTPUT_ROUTE_SENTINEL\n',self.r,{})
 def test_bad_stderr(self):
  with self.assertRaises(ValueError):gateway.validate_completed('airis',b'{}',b'warning',self.r,{})
 def test_wrong_worker(self):
  with self.assertRaises(ValueError):gateway.run_native('nars',self.r,'x',outer_deadline=0)
 def test_actual_launcher_pinned(self):
  with patch.object(gateway,'verify_inputs',return_value={'host_launcher_python':'/wrong','files':{}}):
   with self.assertRaisesRegex(ValueError,'Actual host launcher'):gateway.run_native('airis',self.r,'x',outer_deadline=gateway.time.monotonic()+5)

class Boundaries(unittest.TestCase):
 def test_trace_budget(self):
  b=experiment.Bounds('/upstream');b.lines=200000;f=types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename='/upstream',co_name='predict'))
  with self.assertRaisesRegex(RuntimeError,'line budget'):b.trace(f,'line',None)
 def test_trace_forbids_planner(self):
  b=experiment.Bounds('/upstream');f=types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename='/upstream',co_name='make_plan'))
  with self.assertRaisesRegex(RuntimeError,'Planner'):b.trace(f,'call',None)
 def test_other_module_not_counted(self):
  b=experiment.Bounds('/upstream');f=types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename='/other',co_name='x'));b.trace(f,'line',None);self.assertEqual(b.lines,0)
 def test_graph_cap(self):
  a=types.SimpleNamespace(state_graph={i:i for i in range(25)},knowledge={},action_plan=[])
  with self.assertRaises(ValueError):experiment.Bounds('/x').check(a)
 def test_plan_cap(self):
  a=types.SimpleNamespace(state_graph={},knowledge={},action_plan=[1,2])
  with self.assertRaises(ValueError):experiment.Bounds('/x').check(a)
 def test_process_audit(self):
  for event in ('os.system','subprocess.Popen','os.exec','os.fork','os.posix_spawn'):
   with self.assertRaises(PermissionError):worker.file_policy(event,())
 def test_write_escape(self):
  with self.assertRaises(PermissionError):worker.file_policy('open',('/tmp/outside','w',os.O_WRONLY))
 def test_integer_write_fd(self):
  with self.assertRaises(PermissionError):worker.file_policy('open',(1,'w',os.O_WRONLY))
 def test_expected_log_write(self):worker.file_policy('open',('airis logs/x.log','w',os.O_WRONLY))
 def test_read_allowed(self):worker.file_policy('open',('/upstream/source.py','r',0))
 def test_no_upstream_main_effect(self):
  if not (Path(__file__).parents[1]/'upstream/airis.py').is_file():self.skipTest('Pinned original AIRIS source is external')
  tree=ast.parse((Path(__file__).parents[1]/'upstream/airis.py').read_text())
  self.assertTrue(all(isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef)) for n in tree.body))
 def make_logs(self,root):
  for d,prefix in (('airis logs','airis init '),('training logs','training log ')):
   (root/d).mkdir();(root/d/(prefix+'2026-11-09 10-00-00.log')).write_text('synthetic log\n')
 def test_log_audit(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);rows=gateway.audit_work_files(root);self.assertEqual(len(rows),2);self.assertTrue(all(r['bytes']==14 for r in rows))
 def test_unexpected_file_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);(root/'extra').write_text('x')
   with self.assertRaises(ValueError):gateway.audit_work_files(root)
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);p=next((root/'airis logs').iterdir());p.unlink();p.symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):gateway.audit_work_files(root)
 def test_oversize_log_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);next((root/'airis logs').iterdir()).write_bytes(b'x'*262145)
   with self.assertRaises(ValueError):gateway.audit_work_files(root)

 def test_duplicate_log_directory_rejected_with_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);next((root/'training logs').iterdir()).unlink();(root/'airis logs/airis init 2026-11-09 10-00-01.log').write_text('second')
   with self.assertRaises(gateway.WorkOutputError) as caught:gateway.audit_work_files(root)
   self.assertEqual(len(caught.exception.evidence),2);self.assertTrue(all('sha256' in r for r in caught.exception.evidence))
 def test_partial_constructor_log_evidence_retained(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);next((root/'training logs').iterdir()).unlink()
   with self.assertRaises(gateway.WorkOutputError) as caught:gateway.audit_work_files(root)
   self.assertEqual(len(caught.exception.evidence),1);self.assertEqual(caught.exception.evidence[0]['tail_utf8'],'synthetic log\n')
 def test_unexpected_file_preserves_known_log_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.make_logs(root);(root/'surprise').write_text('x')
   with self.assertRaises(gateway.WorkOutputError) as caught:gateway.audit_work_files(root)
   self.assertEqual(len(caught.exception.evidence),2)

 def import_fixture(self):
  from paths import HERE,PYTHON
  paths=[str(p) for p in (HERE/'contract.py',HERE/'experiment.py',HERE/'runtime_guard.py',HERE/'paths.py',PYTHON/'lib/python3.12/json/__init__.py',PYTHON/'lib/python3.12/logging/__init__.py')]
  proof={k:str(PYTHON) for k in ('prefix','exec_prefix','base_prefix','base_exec_prefix')}
  proof.update(search_path=[str(HERE),str(PYTHON/'lib/python312.zip'),str(PYTHON/'lib/python3.12'),str(PYTHON/'lib/python3.12/lib-dynload')],flags={'safe_path':True,'no_user_site':1,'no_site':1,'dont_write_bytecode':1},imported_files={p:'1'*64 for p in paths})
  return proof,{'files':{p:{'sha256':'1'*64} for p in paths}}
 def test_bound_import_proof(self):
  p,l=self.import_fixture();gateway.validate_import_proof(p,l)
 def test_fallback_prefix_rejected(self):
  p,l=self.import_fixture();p['exec_prefix']='/usr'
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_fallback_search_path_rejected(self):
  p,l=self.import_fixture();p['search_path'].append('/usr/lib/python3.12')
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_user_site_enabled_rejected(self):
  p,l=self.import_fixture();p['flags']['no_user_site']=0
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_unpinned_import_rejected(self):
  p,l=self.import_fixture();p['imported_files']['/usr/lib/python3.12/json/__init__.py']='1'*64
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_changed_import_hash_rejected(self):
  p,l=self.import_fixture();p['imported_files'][next(iter(p['imported_files']))]='2'*64
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_missing_import_rejected(self):
  p,l=self.import_fixture();p['imported_files'].pop(next(iter(p['imported_files'])))
  with self.assertRaises(ValueError):gateway.validate_import_proof(p,l)
 def test_launcher_binds_home_without_ignoring_it(self):
  tree=ast.parse((Path(__file__).parent/'launch.py').read_text());text=ast.unparse(tree)
  self.assertIn("'PYTHONHOME': str(PYTHON)",text);self.assertIn("'-P', '-s', '-S', '-B'",text);self.assertNotIn("'-I'",text)

class Lifecycle(unittest.TestCase):
    def test_owned_signal_precedes_reap(self):
        events=[]
        class P:
            pid=123;returncode=None
            def wait(self,timeout):events.append('reap');self.returncode=0;return 0
        with patch.object(gateway,'observed_exit',side_effect=lambda p:events.append('observe')),patch.object(gateway.os,'killpg',side_effect=lambda p,s:events.append('signal')):
            self.assertTrue(gateway.stop_owned(P(),gateway.time.monotonic()+1)['reaped'])
        self.assertEqual(events,['observe','signal','reap'])
    def test_reaped_never_signalled(self):
        class P:pid=123;returncode=0
        with patch.object(gateway.os,'killpg',side_effect=AssertionError('stale signal')):self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'already-reaped')
    def test_lost_never_signalled(self):
        class P:pid=123;returncode=None
        with patch.object(gateway,'observed_exit',side_effect=ChildProcessError()),patch.object(gateway.os,'killpg',side_effect=AssertionError('stale signal')):self.assertEqual(gateway.stop_owned(P(),1)['ownership'],'lost')
    def test_deferred_cancel_delivered(self):
        class Cancel(BaseException):pass
        def handler(n,f):raise Cancel()
        with self.assertRaises(Cancel):gateway.replay_deferred_signal({signal.SIGTERM:handler},[signal.SIGTERM])
    def test_deferred_default(self):
        with self.assertRaises(InterruptedError):gateway.replay_deferred_signal({signal.SIGTERM:signal.SIG_DFL},[signal.SIGTERM])
    def test_no_deferred_signal(self):gateway.replay_deferred_signal({},[])
    def test_successful_child_cleanup_failure_keeps_receipt(self):
        class Work:
            def __enter__(self):return '/pure-work'
            def __exit__(self,*args):raise OSError('cleanup failed')
        receipt={'status':'passed','native_tested':True,'stdout':'actual-prefix'}
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(OSError) as caught:
                with gateway.temporary_work({'receipt':receipt}):pass
        self.assertIs(caught.exception.receipt,receipt)
        self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['temporary_cleanup'],'uncertain')
        self.assertEqual(receipt['stdout'],'actual-prefix')
    def test_native_error_and_cleanup_failure_preserve_primary(self):
        class Work:
            def __enter__(self):return '/pure-work'
            def __exit__(self,*args):raise OSError('cleanup failed')
        receipt={'status':'failed','error':'native failure','returncode':1}
        primary=RuntimeError('original native failure');primary.receipt=receipt
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(RuntimeError) as caught:
                with gateway.temporary_work({'receipt':receipt}):raise primary
        self.assertIs(caught.exception,primary);self.assertIs(caught.exception.receipt,receipt)
        self.assertIn('original native failure',receipt['primary_error']);self.assertIn('cleanup failed',receipt['temporary_cleanup_error'])
    def test_cancellation_class_survives_cleanup_failure(self):
        class Cancel(BaseException):pass
        class Work:
            def __enter__(self):return '/pure-work'
            def __exit__(self,*args):raise OSError('cleanup failed')
        receipt={'status':'failed','stdout':'native-prefix'};primary=Cancel('cancelled');primary.receipt=receipt
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(Cancel) as caught:
                with gateway.temporary_work({'receipt':receipt}):raise primary
        self.assertIs(caught.exception,primary);self.assertIs(caught.exception.receipt,receipt)
        self.assertEqual(receipt['temporary_cleanup'],'uncertain')
    def test_clean_directory_preserves_primary_without_false_cleanup_error(self):
        class Work:
            def __enter__(self):return '/pure-work'
            def __exit__(self,*args):return False
        receipt={'status':'failed'};primary=RuntimeError('native failed');primary.receipt=receipt
        with patch.object(gateway.tempfile,'TemporaryDirectory',return_value=Work()):
            with self.assertRaises(RuntimeError) as caught:
                with gateway.temporary_work({'receipt':receipt}):raise primary
        self.assertIs(caught.exception,primary);self.assertNotIn('temporary_cleanup_error',receipt)


if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('Native process forbidden in pure tests')),patch('os.execve',side_effect=AssertionError('Native exec forbidden')):
        unittest.main(verbosity=2)
