"""Exercise genuine CLI/StateStore on temporary host files; no image or VM."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import check
import build

class ActualControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.umask=os.umask(0o077)
        self.patches=[patch.object(check,'CLI',build.ROOT/'scripts/roko.py'),patch.object(check,'DIRECTORY',self.root/'roko-state'),patch.object(check,'RECEIPT',self.root/'verification.json')]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        os.umask(self.umask); self.temp.cleanup()
    def run_phase(self,phase):
        with contextlib.redirect_stdout(io.StringIO()) as out: check.run(phase)
        return out.getvalue()
    def test_real_cli_write_then_read(self):
        self.assertIn('REJECTION_PASSED',self.run_phase('write'))
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertIn('READ_PASSED tasks=2 revisions=7,2 actions=0',self.run_phase('read'))
        after={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_write_refuses_existing_state_directory(self):
        check.DIRECTORY.mkdir(mode=0o700)
        with self.assertRaises(FileExistsError): self.run_phase('write')
    def test_corruption_is_rejected_by_actual_store(self):
        self.run_phase('write')
        path=next(p for p in check.DIRECTORY.glob('*.json') if check.TASK.encode() in p.read_bytes())
        path.write_bytes(path.read_bytes().replace(b'Arithmetic: 7 * 8.',b'Arithmetic: 7 * 9.'))
        with self.assertRaises(RuntimeError): self.run_phase('read')
    def test_missing_recovery_receipt_fails(self):
        with self.assertRaises(FileNotFoundError): self.run_phase('read')

class ArchiveTests(unittest.TestCase):
    def test_unpack_preserves_payload_and_metadata(self):
        import stat
        raw=build.archive.entry('bin/sh',b'busybox',stat.S_IFLNK|0o777,1)+build.archive.entry('TRAILER!!!',b'',0,2)
        self.assertEqual(build.unpack(raw),{'bin/sh':(b'busybox',stat.S_IFLNK|0o777,0,0)})
    def test_unpack_rejects_corruption(self):
        with self.assertRaises(ValueError): build.unpack(b'invalid')
    def test_distinct_fixed_disk_identity(self):
        import image
        self.assertEqual(image.UUID,'726f6b6f-7374-4164-8000-000000000002')
        self.assertIn("'cognitive-filesystem-guest'",(build.HERE/'image.py').read_text())
        self.assertIn('roko-cognitive-state',image.attach(5)[-1])

if __name__=='__main__': unittest.main()
