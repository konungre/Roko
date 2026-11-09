import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import prepare

class PreparationTests(unittest.TestCase):
    def test_candidate_disabled_and_no_weight_copy(self):
        m=json.loads((prepare.OUT/'host-companion.lock.json').read_text())
        self.assertEqual(m['status'],'host-companion-source-only-awaiting-execution-grant')
        self.assertFalse(m['optimized_loader_admitted'])
        for path,expected in m['files'].items():
            self.assertEqual(hashlib.sha256((prepare.OUT/path).read_bytes()).hexdigest(),expected)
        self.assertFalse(any('gguf' in p for p in m['external_files']))
    def test_native_host_python_is_exact_and_children_use_wrapper(self):
        r=subprocess.run([str(prepare.OUT/'runtime/python313'),'-c','import sys;print(sys.version_info[:3])'],capture_output=True,text=True,timeout=5,check=True)
        self.assertEqual(r.stdout.strip(),'(3, 13, 5)')
        text=(prepare.OUT/'adapters/runtime_select.py').read_text()
        self.assertIn("str(root / 'runtime/python313')",text)
        self.assertIn("'--seconds', '60'",text)
    def test_network_guard_and_actual_negative_cli_only(self):
        # Reputable existing child-only seccomp wrapper. No model start/run.
        with tempfile.TemporaryDirectory(dir=ROOT/'results/granite-host-companion-preparation') as tmp:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/no-network.py'),str(prepare.OUT/'runtime/python313'),
                str(HERE/'profile.py'),'--root',str(prepare.OUT),'--out',str(Path(tmp)/'negative')],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads((Path(tmp)/'negative/evaluation.json').read_text())
            self.assertTrue(report['wrong_proposal_fixture']['rejected'])
            self.assertEqual(report['model_runs_performed'],0)
    def test_cancel_identity_rejects_supervisor_argv_and_requires_model_map(self):
        from native_identity import native_identity
        closure=Path('/fixed/closure');loader=str(closure/'system/ld-linux-x86-64.so.2');helper=str(closure/'avx2/infer');model='/fixed/weights'
        argv=[loader,'--library-path','/fixed/libs',helper,'--model','/proc/123/fd/4']
        maps={loader,helper,model}
        self.assertIsNotNone(native_identity(argv,loader,maps,closure,model))
        supervisor=['/python/loader','/python/bin/python3.13','/supervise.py','--',*argv]
        self.assertIsNone(native_identity(supervisor,'/python/loader',maps,closure,model))
        self.assertIsNone(native_identity(argv,loader,{loader,helper},closure,model))
        self.assertIsNone(native_identity(argv,loader,{loader,model},closure,model))
        self.assertIsNone(native_identity(argv,'/wrong/executable',maps,closure,model))

    def test_actual_bridge_bytes_unchanged(self):
        self.assertEqual(hashlib.sha256((prepare.OUT/'avatar/task_bridge.py').read_bytes()).hexdigest(),
                         '282c922de9615bb5126de029cb36ba7a49ff100c392cba8fffcc3a06915a0b3d')

if __name__=='__main__':unittest.main()
