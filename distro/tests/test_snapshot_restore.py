import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'session'))
import state_image


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'snapshot'
        with self.source.open('xb') as f: f.truncate(state_image.SIZE)
        self.source.chmod(0o600)
        with self.source.open('rb') as f: self.sha = hashlib.file_digest(f, 'sha256').hexdigest()
        self.output = self.root/'restored'

    def restore(self, **kwargs):
        return state_image.restore(self.source, self.output, self.sha, **kwargs)

    def test_copy_is_private_independent_and_attachable(self):
        result = self.restore()
        fd = state_image.open_image(self.output)
        try:
            self.assertNotEqual(os.fstat(fd).st_ino, self.source.stat().st_ino)
            os.pwrite(fd, b'changed', 0)
            with self.source.open('rb') as original: self.assertEqual(original.read(7), bytes(7))
        finally: os.close(fd)
        self.assertFalse(result['guest_read_tested'])
        with self.assertRaises(FileExistsError): self.restore()

    def test_digest_failure_never_publishes(self):
        self.sha = 'f' * 64
        with self.assertRaises(ValueError): self.restore()
        self.assertFalse((self.output/'state.raw').exists())
        with self.assertRaises(FileNotFoundError): state_image.open_image(self.output)

    def test_interruptions_before_publication_never_attach(self):
        for phase in ('copy-durable', 'copy-verified'):
            self.output = self.root/phase
            def stop(actual):
                if actual == phase: raise OSError('injected interruption')
            with self.assertRaises(OSError): self.restore(checkpoint=stop)
            with self.assertRaises(FileNotFoundError): state_image.open_image(self.output)
            with self.assertRaises(FileExistsError): self.restore()

    def test_links_and_public_snapshot_refused(self):
        self.source.chmod(0o644)
        with self.assertRaises(ValueError): self.restore()
        self.source.chmod(0o600)
        os.link(self.source, self.root/'alias')
        with self.assertRaises(ValueError): self.restore()
        self.assertFalse(self.output.exists())
