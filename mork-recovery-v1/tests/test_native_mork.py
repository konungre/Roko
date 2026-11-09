import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'source'))
import native_mork as m

class NativeMORKTests(unittest.TestCase):
    def facts(self): return [{'relation':'friend', 'args':['sam','tim']}]
    def query(self): return {'relation':'friend','args':['sam',None]}
    def output(self, rows): return ('MORK_FACTS_V1\n'+rows+'MORK_END\n').encode('ascii')
    def encoded(self):
        facts,query=m._validate(self.facts(),self.query(),3)
        request,decode=m._encode(facts,query)
        return facts,query,request,decode
    def test_detached_validation(self):
        facts=self.facts(); query=self.query();original=copy.deepcopy((facts,query))
        f,q=m._validate(facts,query,3);f[0]['args'][0]='other';q['args'][0]='other'
        self.assertEqual((facts,query),original)
    def test_zero_and_maximum_fact_counts(self):
        for facts in [[],[{'relation':'r','args':['a'+str(i)]} for i in range(16)]]:
            m._validate(facts,{'relation':'r','args':[None]},3)
        for facts in [self.facts()*17,(),None]:
            with self.assertRaises(ValueError):m._validate(facts,self.query(),3)
    def test_bad_symbol_inputs(self):
        for symbol in ['', 'A','1x','é','a b','a\n','a\x00','a) !(system bad)', '$v','a/b','a'*17,True,1,{},None]:
            with self.subTest(symbol=symbol):
                facts=self.facts();facts[0]['args'][0]=symbol
                with self.assertRaises(ValueError):m._validate(facts,self.query(),3)
    def test_query_injection_rejected(self):
        for value in ['$', 'a)','"x"', ['x'],True]:
            query=self.query();query['args'][1]=value
            with self.assertRaises(ValueError):m._validate(self.facts(),query,3)
    def test_arity_boundaries(self):
        for count in [1,3]:m._validate([{'relation':'r','args':['a']*count}],{'relation':'r','args':[None]*count},3)
        for count in [0,4]:
            with self.assertRaises(ValueError):m._validate([],{'relation':'r','args':[None]*count},3)
    def test_consistent_relation_arity(self):
        with self.assertRaises(ValueError):m._validate(self.facts(),{'relation':'friend','args':[None]},3)
    def test_exact_fields_and_types(self):
        for row in [{'relation':'r'}, {'relation':'r','args':['a'],'execute':True}, [], {'relation':'r','args':('a',)}]:
            with self.assertRaises(ValueError):m._validate([row],self.query(),3)
    def test_timeout_bounds(self):
        for timeout in [0,6,True,1.0,'1',None]:
            with self.assertRaises(ValueError):m._validate(self.facts(),self.query(),timeout)
        for timeout in [1,5]:m._validate(self.facts(),self.query(),timeout)
    def test_typed_byte_ceiling(self):
        size=len(json.dumps({'facts':self.facts(),'query':self.query()},separators=(',',':')).encode('ascii'))
        with patch.object(m,'MAX_REQUEST_BYTES',size):m._validate(self.facts(),self.query(),3)
        with patch.object(m,'MAX_REQUEST_BYTES',size-1):
            with self.assertRaises(ValueError):m._validate(self.facts(),self.query(),3)
    def test_internal_tokens_only(self):
        _,_,req,_=self.encoded()
        self.assertNotIn('friend',req['atoms']);self.assertNotIn('sam',req['query'])
        self.assertLess(len(req['query']),m.MAX_QUERY_BYTES)
        self.assertNotIn('mm2-exec',str(req))
    def test_generated_byte_ceiling(self):
        f,q,req,_=self.encoded()
        with patch.object(m,'MAX_QUERY_BYTES',len(req['query'])-1):
            with self.assertRaises(ValueError):m._encode(f,q)
        with patch.object(m,'MAX_ATOM_BYTES',len(req['atoms'])-1):
            with self.assertRaises(ValueError):m._encode(f,q)
    def test_decode_correct_fact(self):
        f,q,req,decode=self.encoded()
        self.assertEqual(m._decode(self.output(req['atoms']+'\n'),f,q,decode),f)
    def test_decode_missing_fact_fails(self):
        f,q,_,decode=self.encoded()
        with self.assertRaises(m.NativeMORKError):m._decode(self.output(''),f,q,decode)
    def test_decode_duplicates_fail(self):
        f,q,req,decode=self.encoded()
        with self.assertRaises(m.NativeMORKError):m._decode(self.output((req['atoms']+'\n')*2),f,q,decode)
    def test_decode_bad_protocol_and_symbols(self):
        f,q,req,decode=self.encoded()
        for raw in [b'',b'ERR: failed',b'\xff',b'MORK_FACTS_V1\n',b'MORK_FACTS_V1\nMORK_END',self.output('(s999 s0)\n'),self.output('(exec bad)\n'),self.output(req['atoms']),self.output('\n'),self.output('a'*1025),self.output((req['atoms']+'\n')*17)]:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(m.NativeMORKError):m._decode(raw,f,q,decode)
    def test_decode_reject_extra_fact(self):
        f,q,req,decode=self.encoded();decode['s99']='other'
        with self.assertRaises(m.NativeMORKError):m._decode(self.output('(s99 s1 s2)\n'),f,q,decode)
    def test_unavailable_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(m.NativeMORKError,'unavailable'):m.query_facts(self.facts(),self.query(),root=root)
    def test_bad_binary_hash_fails_before_process(self):
        with tempfile.TemporaryDirectory() as root:
            binary=Path(root)/'build-src/mork-stage/PeTTa/mork_ffi/target/release/libmork_ffi.so'
            binary.parent.mkdir(parents=True);binary.write_bytes(b'changed')
            with patch.object(m.subprocess,'Popen') as process:
                with self.assertRaisesRegex(m.NativeMORKError,'hash mismatch'):m.query_facts(self.facts(),self.query(),root=root)
                process.assert_not_called()
    def test_invalid_input_never_spawns(self):
        with patch.object(m.subprocess,'Popen') as process:
            with self.assertRaises(ValueError):m.query_facts([{'relation':'evil)','args':['x']}],self.query())
            process.assert_not_called()
    def run_child(self, code, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            return m._run([sys.executable,'-c',code],b'x\n',cwd=directory,env={'PATH':'/usr/bin:/bin'},timeout=timeout)
    def test_process_success(self):self.assertEqual(self.run_child("import sys;sys.stdin.read();print('ok')"),b'ok\n')
    def test_process_timeout(self):
        with self.assertRaisesRegex(m.NativeMORKError,'timed out'):self.run_child('import time;time.sleep(5)',timeout=1)
    def test_cleanup_even_after_leader_exits(self):
        with patch.object(m, '_kill', wraps=m._kill) as kill:
            self.assertEqual(self.run_child("print('ok')"), b'ok\n')
            kill.assert_called_once()
    def test_descendant_pipe_timeout_kills_group(self):
        code = "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])"
        with patch.object(m, '_kill', wraps=m._kill) as kill:
            with self.assertRaisesRegex(m.NativeMORKError, 'timed out'):
                self.run_child(code, timeout=1)
            kill.assert_called_once()
    def test_closed_stream_timeout(self):
        with self.assertRaisesRegex(m.NativeMORKError, 'timed out'):
            self.run_child('import os,time;os.close(1);os.close(2);time.sleep(5)', timeout=1)
    def test_closed_pipe_descendant_is_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory)/'descendant.pid'
            child = 'import time;time.sleep(10)'
            code = ("import subprocess,sys,pathlib; p=subprocess.Popen([sys.executable,'-c',"+repr(child)+"], "
                    "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                    "pathlib.Path("+repr(str(pidfile))+").write_text(str(p.pid)); print('ok')")
            output = m._run([sys.executable,'-c',code], b'x\n', cwd=directory, env={'PATH':'/usr/bin:/bin'}, timeout=2)
            self.assertEqual(output,b'ok\n')
            pid=int(pidfile.read_text())
            # A killed orphan can briefly remain as a zombie until init reaps it.
            import time
            for _ in range(50):
                try: state=Path('/proc/'+str(pid)+'/stat').read_text().split(') ')[1].split()[0]
                except FileNotFoundError: break
                if state=='Z': break
                time.sleep(0.01)
            else: self.fail('Descendant survived process-group cleanup')
    def test_process_startup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(m.NativeMORKError, 'unavailable'):
                m._run(['/definitely-missing-roko-test-binary'], b'x', cwd=directory, env={}, timeout=1)
    def test_process_nonzero(self):
        with self.assertRaises(m.NativeMORKError):self.run_child('raise SystemExit(2)')
    def test_process_stderr_fails_closed(self):
        with self.assertRaises(m.NativeMORKError):self.run_child("import sys;sys.stderr.write('warning')")
    def test_process_stdout_cap(self):
        with self.assertRaisesRegex(m.NativeMORKError,'output limit'):self.run_child("import sys;sys.stdout.write('x'*10000)")
    def test_process_stderr_cap(self):
        with self.assertRaisesRegex(m.NativeMORKError,'output limit'):self.run_child("import sys;sys.stderr.write('x'*10000)")
    def test_process_exact_stdout_cap(self):
        self.assertEqual(len(self.run_child("import sys;sys.stdout.write('x'*4096)")),4096)

if __name__=='__main__':unittest.main()
