"""Socket metadata fixtures; never a running compositor/bus qualification."""
import os,socket,sys,tempfile,unittest,subprocess,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nix'))
from cosmic_session_report import inspect_session
class CosmicInputsTests(unittest.TestCase):
 def test_complete_fixture_socket_metadata_never_grants_readiness(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);root.chmod(0o700);env={'XDG_CURRENT_DESKTOP':'COSMIC','XDG_SESSION_TYPE':'wayland','XDG_RUNTIME_DIR':name,'WAYLAND_DISPLAY':'wayland-1','DBUS_SESSION_BUS_ADDRESS':'unix:path='+str(root/'bus')}
   sockets=[]
   try:
    for path in (root/'wayland-1',root/'bus'):
     s=socket.socket(socket.AF_UNIX);s.bind(str(path));sockets.append(s)
    report=inspect_session(env);self.assertEqual(report['status'],'inputs-observed-unqualified')
    for key in ('interactive_ready','cosmic_session_qualified','inference_qualified','execution_authorized'):self.assertIs(report[key],False)
    (root/'wayland-1').unlink();self.assertEqual(inspect_session(env)['status'],'incomplete')
   finally:
    for s in sockets:s.close()
 def test_missing_untrusted_paths_and_socket_symlink_stay_incomplete(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);root.chmod(0o755);env={'XDG_CURRENT_DESKTOP':'COSMIC','XDG_SESSION_TYPE':'wayland','XDG_RUNTIME_DIR':name,'WAYLAND_DISPLAY':'../secret','DBUS_SESSION_BUS_ADDRESS':'tcp:host=private-do-not-log'}
   report=inspect_session(env);self.assertFalse(report['checks']['private_runtime']);self.assertNotIn('private-do-not-log',str(report))
   root.chmod(0o700);(root/'ordinary').write_text('not a socket');(root/'wayland-1').symlink_to(root/'ordinary');env.update(WAYLAND_DISPLAY='wayland-1',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'bus'))
   self.assertFalse(inspect_session(env)['checks']['owned_wayland_socket']);self.assertFalse(inspect_session({},uid=0)['checks']['non_root'])
 def test_cli_incomplete_report_is_private_and_unqualified(self):
  with tempfile.TemporaryDirectory() as name:
   output=Path(name)/'status.json';script=Path(__file__).resolve().parents[1]/'nix/cosmic_session_report.py'
   run=subprocess.run([sys.executable,'-B',str(script),'--output',str(output)],capture_output=True,text=True,timeout=3,env={'PATH':'/usr/bin:/bin','XDG_CURRENT_DESKTOP':'private-fixture-do-not-log'})
   self.assertEqual(run.returncode,0,run.stderr);report=json.loads(output.read_text());self.assertEqual(report['status'],'incomplete');self.assertFalse(report['interactive_ready']);self.assertEqual(output.stat().st_mode&0o777,0o600);self.assertNotIn('private-fixture-do-not-log',output.read_text()+run.stdout)
if __name__=='__main__':unittest.main()
