import ast,contextlib,importlib.util,io,json,math,os,sys,tempfile,threading,time,types,unittest
from pathlib import Path
import prepare
FILES,PLAN,DIFFS=prepare.sources(admitted=True)
BP='corner/usr/share/roko/corner/task_bridge.py'
def bridge():
 m=types.ModuleType('combined_bridge');exec(compile(FILES[BP][0],BP,'exec'),m.__dict__);return m
class Tests(unittest.TestCase):
 def test_finite_bridge_caps_and_default(self):
  b=bridge();self.assertEqual(b.run_task.__kwdefaults__['command_timeout'],120)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'scripts').mkdir();(root/'scripts/roko.py').write_text('')
   for value in (True,False,0,-1,1081,float('inf'),float('-inf'),float('nan'),'1080',None):
    result=b.run_task(root,root/'state','arithmetic','test','Arithmetic: 7 * 8.',command_timeout=value)
    self.assertIn('Command timeout',result['error']);self.assertIsNone(result['task_id'])
 def test_admitted_bridge_reaches_actual_steps(self):
  b=bridge();calls=[]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'scripts').mkdir();(root/'scripts/roko.py').write_text('')
   def run(argv,timeout,event):
    calls.append((argv[4],timeout));task=argv[5];return 0,json.dumps({'state':{'task_id':task,'executed_actions':0,'phase':'evidence'}}),''
   b._run=run
   result=b.run_task(root,root/'state','arithmetic','test','Arithmetic: 7 * 8.',command_timeout=1080)
   self.assertIsNone(result['error']);self.assertEqual([c[0] for c in calls],['create','evidence','infer','check','show']);self.assertEqual(calls[-1][1],10)
 def test_raw_guard_cases(self):
  tree=ast.parse(FILES['roko/scripts/roko.py'][0]);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='infer');end=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='update');fn.body=fn.body[:end]
  module=ast.Module(body=[fn],type_ignores=[]);ast.fix_missing_locations(module)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'vendor/PeTTa/repos/Omega/src').mkdir(parents=True);(root/'vendor/PeTTa/repos/Omega/src/providers.py').write_text('')
   (root/'granite-model.lock.json').write_text(json.dumps({'path':'missing.gguf'}));scope={'ROOT':root,'json':json};exec(compile(module,'guard','exec'),scope)
   with self.assertRaises(ValueError):scope['infer'](None,None)
   (root/'granite-raw-transport.lock.json').write_text(json.dumps({'status':'wrong','reviewed_admission':True}));(root/'granite-portable-runtime.lock.json').write_text('{}')
   with self.assertRaises(ValueError):scope['infer'](None,None)
   raw={'status':'raw-model-transport-admitted','reviewed_admission':True};(root/'granite-raw-transport.lock.json').write_text(json.dumps(raw));runtime={'status':'candidate-runtime-admitted-for-single-probe','files':{'granite-raw-transport.lock.json':'wrong'}};(root/'granite-portable-runtime.lock.json').write_text(json.dumps(runtime))
   with self.assertRaises(ValueError):scope['infer'](None,None)
   runtime['files']['granite-raw-transport.lock.json']=prepare.sha((root/'granite-raw-transport.lock.json').read_bytes());(root/'granite-portable-runtime.lock.json').write_text(json.dumps(runtime));scope['infer'](None,None)
 def test_diagnostics_preserve_json_stdout(self):
  provider=FILES['roko/adapters/granite_guest.py'][0].decode();self.assertIn('file=sys.stderr, flush=True)',provider)
  b=bridge();task='check';state={'task_id':task,'executed_actions':0,'phase':'verified'}
  code,out,err=b._run([sys.executable,'-c',"import json,sys; print('ROKO_GRANITE_GUEST_OBSERVATION diagnostic',file=sys.stderr); print(json.dumps({'raw_model_output':'inert fixture'})); print("+repr(json.dumps({'state':state}))+')'],2,None)
  self.assertEqual(code,0);self.assertEqual(b._snapshot(out,task),state);self.assertIn('OBSERVATION',err)
 def test_closure_and_authority(self):
  runtime=json.loads(FILES['roko/granite-portable-runtime.lock.json'][0])
  for name,digest in runtime['files'].items():self.assertEqual(prepare.sha(FILES['roko/'+name][0]),digest,name)
  for name in ('working_state.py','state_store.py'):self.assertEqual(FILES['roko/adapters/'+name][0],(prepare.R/'adapters'/name).read_bytes())
  self.assertNotIn('roko/adapters/runtime_select.py',DIFFS);self.assertNotIn('roko/runtime/granite/supervise.py',DIFFS)
  self.assertIn(b'command_timeout=120',FILES[BP][0]);self.assertIn(b'1080',FILES['env.sh'][0]);self.assertIn(b'$BB sleep 1410',FILES['session-init'][0])
 def test_cancellation_cross_session(self):
  b=bridge();stage=prepare.OUT/'roko'
  if not stage.exists():self.skipTest('Freeze required for exact staged runtime lifecycle test')
  probe=prepare.load('test_combined_supervisor',stage/'runtime/granite/supervise.py')
  prior=prepare.load('inert_cleanup_fixture',prepare.R/'boot/granite-portable/test_bridge_cleanup.py')
  for cancel in (True,False):
   with tempfile.TemporaryDirectory() as tmp:
    pids=Path(tmp)/'pids.json';event=threading.Event()
    def trigger():
     until=time.monotonic()+5
     while not pids.exists() and time.monotonic()<until:time.sleep(.01)
     event.set()
    thread=threading.Thread(target=trigger) if cancel else None
    if thread:thread.start()
    try:
     with self.assertRaises(b.BridgeError):b._run([sys.executable,'-c',prior.PARENT,str(stage),str(pids)],5 if cancel else 1,event if cancel else None)
    finally:
     if thread:thread.join(timeout=6)
    self.assertTrue(pids.exists());ids=json.loads(pids.read_text())
    def alive(pid):
     row=probe.process(pid);return bool(row and row['state']!='Z')
    until=time.monotonic()+3
    while any(alive(pid) for pid in ids) and time.monotonic()<until:time.sleep(.02)
    self.assertTrue(all(not alive(pid) for pid in ids));self.assertTrue(alive(os.getpid()))
if __name__=='__main__':unittest.main()
