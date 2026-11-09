#!/usr/bin/env python3
import gzip,hashlib,importlib.util,json,stat,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('avatar_builder',HERE/'build.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
class Tests(unittest.TestCase):
 def test_bounded_genuine_exit(self):
  base=(b.ROOT/'boot/cosmic-session-guest/init.sh').read_bytes()
  derived=b.derive_init(base)
  self.assertIn(b'sleep 390',derived)
  self.assertIn(b'timeout 5 /usr/bin/dbus-send',derived)
  self.assertIn(b'com.system76.CosmicSession.Exit',derived)
  self.assertIn(b'sleep 20',derived)
  self.assertIn(b'ROKO_SESSION_FAILED guest-watchdog',derived)
  with self.assertRaises(ValueError):b.derive_init(derived)
  self.assertIn('ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST',(HERE/'finish.sh').read_text())
  self.assertIn("report['exit_origin']=='fixture'",(HERE/'run.py').read_text())
 def test_direct_fixture_is_explicit(self):
  direct=(HERE/'direct-start.sh').read_text();console=(HERE/'console-fixture.sh').read_text()
  self.assertIn('roko.avatar_fixture=1',direct)
  self.assertIn('[ -S "$socket" ]',direct)
  self.assertIn('exec /usr/bin/roko-avatar-test',direct)
  self.assertIn('roko.avatar_fixture=1',console)
  self.assertIn('/usr/bin/cosmic-term --no-daemon -e /usr/bin/python3.13',console)
  self.assertIn('ROKO_AVATAR_CONSOLE_EXIT',console)
  self.assertNotIn('eval ',console)
 def test_newc_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.gz';p.write_bytes(gzip.compress(b.record('a',b'abc',stat.S_IFREG|0o644,1)+b.record('TRAILER!!!',b'',0,2)))
   self.assertEqual(list(b.read_archive(p)),[('a',b'abc',stat.S_IFREG|0o644,0,0)])
 def test_separate_paths_and_pinned_session(self):
  self.assertNotEqual(b.OUT,b.BASE)
  self.assertEqual(b.BASE.name,'061e179a-passed')
  self.assertIn("'base_initramfs_sha256'",(HERE/'build.py').read_text())
 def test_explicit_real_overlay_and_private_events(self):
  launch=(HERE/'launch.sh').read_text();source=(HERE/'build.py').read_text()
  self.assertIn('--overlay --events /run/user/0/roko/avatar.json',launch)
  self.assertIn('GDK_BACKEND=wayland',launch)
  self.assertIn('chmod 700 /run/user/0/roko',source)
 def test_no_host_listener_or_command_execution(self):
  source=(HERE/'run.py').read_text()
  self.assertIn("'-qmp','stdio'",source)
  self.assertNotIn('shell=True',source)
  self.assertNotIn('socket.listen',source)
  self.assertIn("raise ValueError('Unsupported bounded control",source)
if __name__=='__main__':unittest.main()
