"""Read-only OS observation task and bounded advisory projection tests."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learning import validate_tasks,observation


class OSStateTaskTests(unittest.TestCase):
    def test_only_fixed_imported_query_is_admitted(self):
        task={'component':'os_state','request':{'version':1,'operation':'query_imported_profile'}}
        self.assertEqual(validate_tasks([task]),[task])
        for operation in ('build','activate','rollback','shell'):
            with self.assertRaises(ValueError):
                validate_tasks([{'component':'os_state','request':{'version':1,'operation':operation}}])

    def test_projection_states_unestablished_authority_and_host_state(self):
        text=observation('os_state',{'latest_observation':{'value':{'operation':'build-and-profile-switch'}},
                                    'source_revision':16,'machine':'m'*128})
        self.assertLessEqual(len(text),500)
        self.assertIn('does not establish current-host state',text)
        self.assertIn('No mutation authorized',text)
