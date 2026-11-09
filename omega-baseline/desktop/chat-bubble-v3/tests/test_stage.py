import importlib.util,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stage',P/'stage.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
class StageTests(unittest.TestCase):
 def test_fresh_overlay_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=pathlib.Path(tmp)/'overlay';record=stage.stage(dest)
   self.assertFalse(record['installed']);self.assertFalse(record['omega_runtime_included'])
   for name in ('character.png','corner.png'):
    self.assertEqual((P/'app/assets'/name).read_bytes(),(dest/'usr/share/roko/showcase/assets'/name).read_bytes())
   launcher=(dest/'usr/bin/roko-companion').read_text()
   self.assertIn('--conversation-runner',launcher);self.assertNotIn('--live-request-cli',launcher)
   self.assertIn('Terminal=false',(dest/'etc/xdg/autostart/roko-companion.desktop').read_text())
   with self.assertRaises(FileExistsError):stage.stage(dest)
