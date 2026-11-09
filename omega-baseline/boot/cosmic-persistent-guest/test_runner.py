import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('persistent_runner_test',HERE/'run.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
class Q:
 def __init__(self):self.events=[]
 def key(self,k):self.events.append(('key',k))
 def chord(self,m,k):self.events.append(('chord',m,k))
class Tests(unittest.TestCase):
 def test_all_real_commands_keyboard_supported(self):
  q=Q()
  with patch.object(r.time,'sleep'):
   for command in r.COMMANDS:r.type_text(q,command)
  self.assertIn(('chord','shift','apostrophe'),q.events)
  self.assertIn(('chord','shift','bracket_left'),q.events)
  self.assertIn(('chord','shift','d'),q.events)
  self.assertIn(('chord','shift','8'),q.events)
 def test_keyboard_bounds(self):
  for value in ['x'*513,'\n','é']:
   with self.assertRaises(ValueError):r.type_text(Q(),value)
 def test_descriptor_and_lifecycle_gates(self):
  source=(HERE/'run.py').read_text()
  for required in ['pass_fds=(fd,)','storage.admitted()','storage.fsck(fd)','storage.validate_pair','ROKO_DESKTOP_STORAGE_UNMOUNTED','ROKO_AVATAR_CONSOLE_EXIT 0',"typed('quit')"]:self.assertIn(required,source)
  self.assertNotIn('shell=True',source)
  self.assertNotIn('socket.listen',source)
  self.assertIn("if not value['automated_passed']:break",source)
 def test_no_state_mutation_in_runner(self):
  source=(HERE/'run.py').read_text()
  self.assertNotIn('StateStore(',source)
  self.assertNotIn('write_bytes(',source)
  self.assertIn('typed(text)',source)
if __name__=='__main__':unittest.main()
