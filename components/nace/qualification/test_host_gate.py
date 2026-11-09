"""Gate preparation and rejection tests; no NACE worker execution."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import run_host_slice as gate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)/'gate'
        self.admission=gate.prepare(self.directory)

    def test_preparation_does_not_import_native_slice(self):
        self.assertNotIn('nace_slice',sys.modules)
        self.assertFalse((self.directory/'observed').exists())
        manifest=json.loads((self.directory/'manifest.json').read_bytes())
        self.assertEqual(len(manifest['cases']),12)
        self.assertFalse(manifest['native_executed'])

    def test_manifest_mismatch_cannot_launch(self):
        with patch.object(gate.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(ValueError,'digest'):
                gate.run(self.directory,'0'*64)

    def test_source_change_cannot_launch(self):
        with patch.object(gate,'frozen_files',return_value={}),patch.object(gate.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(ValueError,'files changed'):
                gate.run(self.directory,self.admission)

    def test_changed_fixture_cannot_launch_even_with_new_digest(self):
        path=self.directory/'manifest.json'
        manifest=json.loads(path.read_bytes());manifest['cases'][0]['request']['now']=900
        path.write_bytes(gate.encode(manifest))
        with patch.object(gate.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(ValueError,'cases changed'):
                gate.run(self.directory,gate.digest(path.read_bytes()))

    def test_run_attempt_cannot_be_overwritten(self):
        (self.directory/'observed').mkdir()
        with patch.object(gate.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaises(FileExistsError):gate.run(self.directory,self.admission)

    def test_numeric_comparison_does_not_coerce_booleans_or_hide_nonfinite(self):
        self.assertFalse(gate.equivalent(True,1))
        self.assertFalse(gate.equivalent(float('nan'),0.5))
        self.assertFalse(gate.equivalent(0.51,0.5))
        self.assertTrue(gate.equivalent(0.5+1e-14,0.5))


if __name__=='__main__':unittest.main()
