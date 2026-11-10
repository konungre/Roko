import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WORKER='''import json,sys,package_planning as p
r=json.load(sys.stdin);s=p.SnapshotOnly(r['snapshot']);a=s.observe();a.packages.clear()
report=p.plan_source(r['desired'],r['snapshot']);print(json.dumps({'report':report,'snapshot':s.observe().document(),'identity':s.identity,'legacy_imported':'omega_pm.core' in sys.modules}))'''
class DirectMigrationTests(unittest.TestCase):
 def test_multi_package_complete_plan_and_snapshot_parity(self):
  a='/nix/store/'+'0'*32+'-a';b='/nix/store/'+'1'*32+'-b';snapshot=json.dumps({'packages':{'hello':b,'extra':a},'revision':'fixture','source':'direct-migration'});desired={'hello':a,'new':b}
  results=[]
  for mode in ('legacy','successor-v2'):
   source='(omega-config 1)\n'+''.join('(package '+k+' '+json.dumps(v)+')\n' for k,v in desired.items()) if mode=='legacy' else json.dumps({'schema':'roko-snapshot-desired-v2','packages':desired})
   r=subprocess.run([sys.executable,'-B','-c',WORKER],input=json.dumps({'snapshot':snapshot,'desired':source}),env={**os.environ,'PYTHONPATH':str(ROOT/'omega-baseline/adapters'),'ROKO_PACKAGE_PLANNER':mode},capture_output=True,text=True,timeout=10)
   self.assertEqual(r.returncode,0,r.stderr);results.append(json.loads(r.stdout))
  old,new=results;self.assertEqual(old['report']['plan'],new['report']['plan']);self.assertEqual(old['snapshot'],new['snapshot']);self.assertEqual(old['identity'],new['identity']);self.assertFalse(new['legacy_imported']);self.assertFalse(new['report']['authorizes_actions'])
 def test_read_only_cli_requires_explicit_selection_and_rejects_apply(self):
  cli=ROOT/'omega-baseline/integration/package_snapshot_cli.py'
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);desired=root/'desired.json';snapshot=root/'snapshot.json';desired.write_text(json.dumps({'schema':'roko-snapshot-desired-v2','packages':{}}));snapshot.write_text(json.dumps({'packages':{},'revision':'0','source':'fixture'}));before=(desired.read_bytes(),snapshot.read_bytes())
   args=[sys.executable,'-B',str(cli),'--desired',str(desired),'--snapshot',str(snapshot)]
   self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
   r=subprocess.run(args+['--planner','successor-v2'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(json.loads(r.stdout)['authorizes_actions'])
   self.assertNotEqual(subprocess.run(args+['--planner','successor-v2','--apply'],capture_output=True).returncode,0);self.assertEqual(before,(desired.read_bytes(),snapshot.read_bytes()))
 def test_successor_rejects_legacy_text_without_silent_evaluation(self):
  code="import package_planning as p; p.plan_source('(omega-config 1)', '{}')"
  r=subprocess.run([sys.executable,'-B','-c',code],env={**os.environ,'PYTHONPATH':str(ROOT/'omega-baseline/adapters'),'ROKO_PACKAGE_PLANNER':'successor-v2'},capture_output=True)
  self.assertNotEqual(r.returncode,0)
