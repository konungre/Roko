"""Synthetic regular-file and mount-parser tests only. No model/native run."""
import hashlib
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import media_transport as media

ROW = b'55 22 7:0 / /run/roko-live-media ro,nosuid,nodev - iso9660 /dev/sr0 ro\n'


class Tests(unittest.TestCase):
    def test_exact_readonly_mount(self):
        row = media.mount_record(ROW)
        self.assertEqual(row['mountpoint'], str(media.MOUNT))
        self.assertEqual(row['filesystem'], 'iso9660')
    def test_wrong_mount_and_writable_superblock_rejected(self):
        for raw in (ROW.replace(b' ro,', b' rw,'), ROW.replace(b'/dev/sr0 ro', b'/dev/sr0 rw'),
                    ROW.replace(b'roko-live-media', b'elsewhere'), ROW + ROW,
                    ROW.replace(b'iso9660', b'nfs'), b'bad', b''):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                media.mount_record(raw)
    def test_nested_mount_hiding_model_rejected(self):
        extra = b'56 55 7:1 / /run/roko-live-media/roko/model ro - squashfs /dev/loop1 ro\n'
        with self.assertRaises(ValueError):
            media.mount_record(ROW + extra)
    def test_unrelated_child_mount_not_rejected(self):
        extra = b'56 55 7:1 / /run/roko-live-media/elsewhere ro - squashfs /dev/loop1 ro\n'
        self.assertEqual(media.mount_record(ROW + extra)['mount_id'], '55')
    def test_mount_escape_parser(self):
        self.assertEqual(media._unescape(r'/hello\040world'), '/hello world')
    def test_exact_synthetic_file_hash_and_length(self):
        with tempfile.TemporaryFile() as f:
            raw = b'SYNTHETIC MODEL TEST ONLY'
            f.write(raw); f.flush()
            report = media._verify_bytes(f.fileno(), len(raw), hashlib.sha256(raw).hexdigest(), 5, clock=lambda: 1)
            self.assertEqual(report['bytes_hashed'], len(raw))
            for size, sha in ((len(raw) + 1, hashlib.sha256(raw).hexdigest()),
                              (len(raw) - 1, hashlib.sha256(raw[:-1]).hexdigest()),
                              (len(raw), '0' * 64)):
                with self.assertRaises(ValueError):
                    media._verify_bytes(f.fileno(), size, sha, 5, clock=lambda: 1)
    def test_deadline_fails(self):
        with tempfile.TemporaryFile() as f:
            f.write(b'x');f.flush()
            with self.assertRaises(TimeoutError):
                media._verify_bytes(f.fileno(), 1, hashlib.sha256(b'x').hexdigest(), 1, clock=lambda: 1)
    def test_fixed_path_open_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'target').write_bytes(b'synthetic')
            (root / 'model').symlink_to(root / 'target')
            with patch.object(media, 'MODEL', root / 'model'), self.assertRaises(OSError):
                media._open_fixed_model()
    def test_fixed_path_walk_rejects_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name);(root/'real').mkdir();(root/'real/model').write_bytes(b'synthetic')
            (root/'alias').symlink_to(root/'real',target_is_directory=True)
            with patch.object(media,'MODEL',root/'alias/model'), self.assertRaises(OSError):
                media._open_fixed_model()
    def test_metadata_rejects_writable_filesystem_even_readonly_fd(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'model';path.write_bytes(b'synthetic')
            fd = os.open(path,os.O_RDONLY)
            try:
                info=os.fstat(fd);mount={'major_minor':f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}'}
                with patch.object(media,'MODEL_BYTES',info.st_size), patch('os.fstatvfs',return_value=types.SimpleNamespace(f_flag=0)), self.assertRaisesRegex(ValueError,'filesystem is not read-only'):
                    media._metadata(fd,mount)
            finally:os.close(fd)
    def test_metadata_rejects_writable_fd(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'model';path.write_bytes(b'synthetic')
            fd=os.open(path,os.O_RDWR)
            try:
                info=os.fstat(fd)
                with patch.object(media,'MODEL_BYTES',info.st_size), self.assertRaisesRegex(ValueError,'descriptor is not read-only'):
                    media._metadata(fd,{'major_minor':'1:2'})
            finally:os.close(fd)
    def test_recheck_never_reopens_or_rebases_changed_identity(self):
        block=media.AdmittedModelFile(91, {'ino':1}, {'mount_id':'55'}, {})
        with patch.object(media,'current_mount',return_value={'mount_id':'56'}), patch.object(media,'_open_fixed_model',side_effect=AssertionError('reopen forbidden')), self.assertRaisesRegex(ValueError,'identity changed'):
            media.recheck_model(block,5)
    def test_closed_descriptor_rejected(self):
        block=media.AdmittedModelFile(None,{}, {}, {})
        with self.assertRaises(ValueError): media.recheck_model(block,5)
    def test_admission_failure_closes_descriptor(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'model';path.write_bytes(b'synthetic')
            fd=os.open(path,os.O_RDONLY)
            with patch.object(media,'current_mount',return_value={}),patch.object(media,'_open_fixed_model',return_value=fd),patch.object(media,'_metadata',side_effect=ValueError('expected guard')):
                with self.assertRaises(ValueError):media.admit_model(Path('/unused'),5)
            with self.assertRaises(OSError):os.fstat(fd)
    def test_descriptor_close_idempotent(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'model';path.write_bytes(b'synthetic')
            fd=os.open(path,os.O_RDONLY);block=media.AdmittedModelFile(fd,{}, {},{})
            block.close();block.close();self.assertIsNone(block.fd)
            with self.assertRaises(OSError):os.fstat(fd)

if __name__=='__main__':unittest.main()
