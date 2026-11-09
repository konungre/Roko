"""Path guards run before writes; spies prevent copying even if guards regress."""
import contextlib,io,pathlib,runpy,sys,tempfile,unittest
from unittest.mock import patch
SCRIPT=pathlib.Path(__file__).with_name('probe_budget_resource_limit.py').resolve()
REPO=SCRIPT.parents[3]
class ReachedCopy(Exception):pass
class ResourceProbePathTests(unittest.TestCase):
 def assert_rejected_before_writes(self,output):
  stderr=io.StringIO();argv=[str(SCRIPT),'--profile','/not-read/profile.json','--source-db','/not-read/source.sqlite','--output',str(output)]
  with patch.object(sys,'argv',argv),patch.object(pathlib.Path,'mkdir',side_effect=AssertionError('Unexpected output creation')) as mkdir,patch('shutil.copytree',side_effect=AssertionError('Unexpected copy')) as copy,contextlib.redirect_stderr(stderr):
   with self.assertRaises(SystemExit) as caught:runpy.run_path(str(SCRIPT),run_name='__main__')
  self.assertEqual(caught.exception.code,2);self.assertIn('outside the repository',stderr.getvalue());mkdir.assert_not_called();copy.assert_not_called()
 def test_direct_checkout_child_rejected(self):self.assert_rejected_before_writes(REPO/'unused-resource-output')
 def test_checkout_itself_rejected(self):self.assert_rejected_before_writes(REPO)
 def test_external_symlink_into_checkout_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   alias=pathlib.Path(temp)/'alias';alias.symlink_to(REPO,target_is_directory=True);self.assert_rejected_before_writes(alias/'unused-output')
 def test_nested_output_under_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   alias=pathlib.Path(temp)/'alias';alias.symlink_to(REPO/'components',target_is_directory=True);self.assert_rejected_before_writes(alias/'conversation'/'unused-output')
 def test_external_output_reaches_nonfollowing_copy_only(self):
  with tempfile.TemporaryDirectory() as temp:
   output=pathlib.Path(temp)/'output';argv=[str(SCRIPT),'--profile','/not-read/profile.json','--source-db','/not-read/source.sqlite','--output',str(output)]
   with patch.object(sys,'argv',argv),patch.object(pathlib.Path,'mkdir') as mkdir,patch('shutil.copytree',side_effect=ReachedCopy) as copy:
    with self.assertRaises(ReachedCopy):runpy.run_path(str(SCRIPT),run_name='__main__')
   mkdir.assert_called_once();copy.assert_called_once();self.assertTrue(copy.call_args.kwargs['symlinks']);self.assertFalse(output.exists())
if __name__=='__main__':unittest.main()
