import unittest
from unittest.mock import patch
from pathlib import Path
import check_runtime


class RuntimeTests(unittest.TestCase):
    def test_observed_registry_versions(self):
        output = "interface: 'zwlr_layer_shell_v1', version: 4, name: 8\ninterface: 'zcosmic_toplevel_info_v1', version: 3, name: 19"
        self.assertEqual(check_runtime.protocol_versions(output), {
            'zwlr_layer_shell_v1': 4, 'zcosmic_toplevel_info_v1': 3})

    def test_library_names_are_not_protocol_evidence(self):
        self.assertEqual(check_runtime.protocol_versions('libgtk-layer-shell.so.0'), {})

    def test_missing_session_never_admitted(self):
        with patch.dict('os.environ', {}, clear=True), patch('shutil.which', return_value=None):
            report = check_runtime.inspect(Path('/nonexistent/companion.py'))
        self.assertFalse(report['ready_for_ui_test'])
        self.assertFalse(report['ready_for_corner_test'])
        self.assertFalse(report['real_omega_verified'])
        self.assertFalse(report['endpoint_executed'])


if __name__ == '__main__':
    unittest.main()
