import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest
import test_signed_release as signatures
import stage_release as staging


class StageTests(unittest.TestCase):
    sign = signatures.SignatureTests.sign
    def setUp(self):
        signatures.SignatureTests.setUp(self)
        self.root.chmod(0o700)
        self.output = self.root/'staged'

    def stage(self, hook=lambda phase: None):
        return staging.stage(self.bundle, self.metadata, self.signature, self.key, 5, self.output, checkpoint=hook)

    def test_stage_and_reauthenticate(self):
        self.stage()
        result = staging.inspect(self.output, self.key, 5)
        self.assertEqual(result['state'], 'authenticated-staging')
        self.assertFalse(result['boot_selected'])
        self.assertEqual((self.output/'bundle.tar').read_bytes(), self.bundle.read_bytes())
        with self.assertRaises(FileExistsError): self.stage()

    def test_every_interruption_boundary(self):
        for phase in ('directory-durable', 'metadata-durable', 'payload-durable', 'copy-authenticated', 'payload-published', 'receipt-durable', 'ready-durable'):
            self.output = self.root/phase
            def fail(actual):
                if actual == phase: raise OSError('injected interrupted write')
            with self.subTest(phase=phase), self.assertRaises(OSError): self.stage(fail)
            result = staging.inspect(self.output, self.key, 5)
            self.assertEqual(result['state'], 'authenticated-staging' if phase == 'ready-durable' else 'incomplete')
            self.assertFalse(result['boot_selected'])
            with self.assertRaises(FileExistsError): self.stage()

    def test_real_process_death_before_receipt(self):
        code = """import os,sys;sys.path.insert(0,sys.argv[1]);import stage_release as s
s.stage(*sys.argv[2:6],5,sys.argv[6],checkpoint=lambda p:os._exit(91) if p=='payload-published' else None)
"""
        result = subprocess.run([sys.executable, '-c', code, str(Path(staging.__file__).parent),
                                 str(self.bundle), str(self.metadata), str(self.signature), str(self.key), str(self.output)], timeout=10)
        self.assertEqual(result.returncode, 91)
        self.assertEqual(staging.inspect(self.output, self.key, 5)['state'], 'incomplete')
        self.assertTrue((self.output/'bundle.tar').is_file())

    def test_source_changed_during_copy(self):
        def change(phase):
            if phase == 'metadata-durable': self.bundle.write_bytes(b'X' * self.value['bytes'])
        with self.assertRaises(ValueError): self.stage(change)
        self.assertFalse((self.output/'READY').exists())

    def test_ready_is_not_trusted(self):
        self.stage()
        (self.output/'bundle.tar').write_bytes(b'X' * self.value['bytes'])
        with self.assertRaises(ValueError): staging.inspect(self.output, self.key, 5)

    def test_new_rollback_floor_rechecked(self):
        self.stage()
        with self.assertRaises(ValueError): staging.inspect(self.output, self.key, 6)

    def test_root_and_public_parent_refused(self):
        with patch.object(staging.os, 'geteuid', return_value=0):
            with self.assertRaises(ValueError): self.stage()
        self.root.chmod(0o755)
        with self.assertRaises(ValueError): self.stage()
        self.assertFalse(self.output.exists())

    def test_no_space_refuses_before_new_directory(self):
        with patch.object(staging.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 0})()):
            with self.assertRaises(ValueError): self.stage()
        self.assertFalse(self.output.exists())
