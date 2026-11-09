"""Contract and mocked lifecycle only. Native program launch is forbidden."""
import copy
import signal
import unittest
from fractions import Fraction
from unittest.mock import patch
import contract as c
import gateway
from run_gate import fixture

class Contract(unittest.TestCase):
    def setUp(self):self.r=fixture('pure_case',(1000,900,1000,900))
    def rows(self):return [{'subject_index':a,'predicate_index':b,'frequency':float(v[0]),'confidence':float(v[1])} for (a,b),v in c.independent_expected(self.r).items()]
    def test_roundtrip_and_detached_copy(self):
        r=c.parse_request(c.canonical(self.r));self.assertEqual(r,self.r);self.assertIsNot(r,self.r)
    def test_independent_known_values(self):
        self.assertEqual(c.independent_expected(self.r),{(0,2):(Fraction(1),Fraction(81,100)),(2,0):(Fraction(1),Fraction(81,181))})
    def test_asymmetric_values(self):
        r=fixture('asymmetric',(500,750,800,600));self.assertEqual(c.independent_expected(r)[(0,2)],(Fraction(2,5),Fraction(9,50)))
    def test_zero_frequency(self):self.assertEqual(c.independent_expected(fixture('zero',(0,999,1000,999)))[(0,2)],(0,0))
    def test_zero_confidence(self):self.assertEqual(c.independent_expected(fixture('zero',(1000,0,1000,999)))[(2,0)],(1,0))
    def test_min_max_fixed_point(self):c.validate_request(fixture('bounds',(0,0,1000,999)))
    def test_unicode_inert_provenance_survives(self):self.assertIn('λ',c.response_from_rows(self.r,self.rows())['premises'][1]['source'])
    def test_no_action_authority(self):
        r=c.response_from_rows(self.r,self.rows());self.assertIs(r['authorizes_actions'],False);self.assertFalse(r['persistent_state_changed']);self.assertFalse(r['full_nars'])
    def test_native_numbers_preserved(self):
        rows=self.rows();rows[0]['frequency']=1;self.assertIs(type(c.response_from_rows(self.r,rows)['conclusions'][0]['frequency']),int)
    def test_order_independent_set(self):self.assertEqual(c.response_from_rows(self.r,self.rows()),c.response_from_rows(self.r,list(reversed(self.rows()))))
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):c.parse_request(b'{"version":1,"version":1}')
    def test_nonfinite_json(self):
        with self.assertRaises(ValueError):c.decode(b'{"x":NaN}',100)
    def test_byte_cap(self):
        with self.assertRaises(ValueError):c.parse_request(b' '*(c.MAX_REQUEST+1))
    def test_unknown_request_field(self):
        r=dict(self.r,code='!(exec)')
        with self.assertRaises(ValueError):c.validate_request(r)
    def test_boolean_revision(self):
        self.r['revision']=True
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_boolean_truth(self):
        with self.assertRaises(ValueError):c.validate_request(fixture('bad',(True,900,1000,900)))
    def test_float_truth(self):
        with self.assertRaises(ValueError):c.validate_request(fixture('bad',(1.0,900,1000,900)))
    def test_outside_truth_bounds(self):
        for values in ((1001,900,1000,900),(1000,1000,1000,900),(-1,900,1000,900)):
            with self.assertRaises(ValueError):c.validate_request(fixture('bad',values))
    def test_bad_premise_hash(self):
        self.r['premises'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def mutate(self,index,key,value):
        p=self.r['premises'][index];p[key]=value;p['sha256']=c.digest(c.premise_payload(p))
    def test_injected_term_rejected(self):
        self.mutate(0,'subject','x) !(exec y)')
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_duplicate_evidence_rejected(self):
        self.mutate(1,'id','evidence_a')
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_cycle_rejected(self):
        self.mutate(1,'predicate','garfield')
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_broken_chain_rejected(self):
        self.mutate(1,'subject','dog')
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_extra_premise_rejected(self):
        self.r['premises'].append(copy.deepcopy(self.r['premises'][0]))
        with self.assertRaises(ValueError):c.validate_request(self.r)
    def test_missing_and_extra_rows(self):
        for rows in ([],self.rows()[:1],self.rows()+self.rows()[:1]):
            with self.assertRaises(ValueError):c.response_from_rows(self.r,rows)
    def test_duplicate_native_conclusion(self):
        with self.assertRaises(ValueError):c.response_from_rows(self.r,[self.rows()[0]]*2)
    def test_wrong_numeric_answer(self):
        rows=self.rows();rows[0]['confidence']=0.82
        with self.assertRaises(ValueError):c.response_from_rows(self.r,rows)
    def test_bad_native_number(self):
        for x in (True,'0.81',float('nan'),float('inf'),-1,2):
            rows=self.rows();rows[0]['confidence']=x
            with self.assertRaises(ValueError):c.response_from_rows(self.r,rows)
    def test_unknown_direction(self):
        rows=self.rows();rows[0]['subject_index']=1
        with self.assertRaises(ValueError):c.response_from_rows(self.r,rows)
    def test_stale_packet_rejected(self):
        packet={'version':1,'request':self.r,'strict_imports':c.MODULES,'native_rows':self.rows(),'response':c.response_from_rows(self.r,self.rows()),'runtime':{},'network_denial_observed':True}
        changed=copy.deepcopy(self.r);changed['revision']=2
        with self.assertRaises(ValueError):c.validate_packet(packet,changed)
    def test_altered_authority_rejected(self):
        packet={'version':1,'request':self.r,'strict_imports':c.MODULES,'native_rows':self.rows(),'response':c.response_from_rows(self.r,self.rows()),'runtime':{},'network_denial_observed':True}
        packet['response']['authorizes_actions']=True
        with self.assertRaises(ValueError):c.validate_packet(packet,self.r)
    def test_no_network_fallback(self):
        packet={'version':1,'request':self.r,'strict_imports':c.MODULES,'native_rows':self.rows(),'response':c.response_from_rows(self.r,self.rows()),'runtime':{},'network_denial_observed':False}
        with self.assertRaises(ValueError):c.validate_packet(packet,self.r)
    def test_unexpected_native_stderr(self):
        with self.assertRaises(ValueError):gateway.validate_completed('nars',b'{}',b'warning',self.r,{})
    def test_parent_enforces_native_packet_cap(self):
        with self.assertRaises(ValueError):gateway.validate_completed('nars',b' '*16385,b'ROKO_NARS_OUTPUT_ROUTE_SENTINEL\n',self.r,{})
    def test_actual_interpreter_bound_before_spawn(self):
        with patch.object(gateway,'verify_inputs',return_value={'host_launcher_python':'/not-the-current-python','files':{}}):
            with self.assertRaisesRegex(ValueError,'Actual host launcher'):gateway.run_native('nars',self.r,'hash',outer_deadline=gateway.time.monotonic()+5)
    def test_other_worker_rejected_before_spawn(self):
        with self.assertRaises(ValueError):gateway.run_native('omega',self.r,'x',outer_deadline=0)

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
