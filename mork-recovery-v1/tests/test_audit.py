import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
import audit


class AuditTests(unittest.TestCase):
    def fixture(self, root):
        data = b'authored fixture\n'
        name = audit.SOURCE_PREFIX + 'fixture.rs'
        path = Path(root) / name
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        row = {'path': name, 'bytes': len(data),
               'git_blob_sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
               'sha256': hashlib.sha256(data).hexdigest()}
        return path, row

    def test_actual_fixture_hash(self):
        with tempfile.TemporaryDirectory() as root:
            _, row = self.fixture(root)
            self.assertEqual(audit.verify_sources([row], root)['files'], 1)

    def test_changed_byte_fails(self):
        with tempfile.TemporaryDirectory() as root:
            path, row = self.fixture(root)
            path.write_bytes(path.read_bytes().replace(b'a', b'z', 1))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit.verify_sources([row], root)

    def test_symlink_fails(self):
        with tempfile.TemporaryDirectory() as root:
            path, row = self.fixture(root)
            actual = path.with_suffix('.actual')
            path.rename(actual); path.symlink_to(actual)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                audit.verify_sources([row], root)

    def test_duplicate_record_fails(self):
        with tempfile.TemporaryDirectory() as root:
            _, row = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                audit.verify_sources([row, row], root)

    def test_missing_runtime_never_becomes_ready(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(audit.check_file(Path(root)/'missing.so', '0'*64)['state'], 'missing')


if __name__ == '__main__': unittest.main()
