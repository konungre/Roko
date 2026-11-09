import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('files_builder_test',H/'build.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
class Tests(unittest.TestCase):
 def test_unique_actual_activation_hook(self):
  self.assertIn(b'/usr/libexec/roko-portal-session-env',b.derive_init(b'session_pid=$!\n'))
  for invalid in [b'',b'session_pid=$!\nsession_pid=$!\n']:
   with self.assertRaises(ValueError):b.derive_init(invalid)
 def test_distinct_output_and_explicit_collision(self):
  self.assertNotEqual(b.OUT,b.BASE);s=(H/'build.py').read_text()
  self.assertIn("if name!=CACHE:raise",s);self.assertIn("output.open('xb')",s)
  self.assertNotIn('subprocess',s)
 def test_test_marker_opt_in_and_actual_environment(self):
  s=(H/'session-env.sh').read_text()
  self.assertIn('roko.files_fixture=1',s);self.assertIn('dbus-update-activation-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR XDG_CURRENT_DESKTOP',s)
  self.assertIn('[ -S "$socket" ]',s)
if __name__=='__main__':unittest.main()
