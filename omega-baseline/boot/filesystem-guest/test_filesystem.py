"""Tiny host unit tests only. No filesystem formatting, VM, mount, or real image."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import image
import build

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        (self.root/'build').mkdir(); self.private=self.root/'build/filesystem-guest'
    def tearDown(self): self.temp.cleanup()
    def create(self):
        # 4 KiB fixtures, never the 64 MiB real image.
        with patch.object(image,'SIZE',4096): return image.open_image(self.root,True)
    def existing(self):
        with patch.object(image,'SIZE',4096): return image.open_image(self.root)
    def test_create_reopen_exclusive_lock(self):
        fd=self.create()
        try:
            self.assertEqual(os.fstat(fd).st_size,4096)
            with self.assertRaises(FileExistsError): self.create()
            with self.assertRaises(BlockingIOError): self.existing()
        finally: os.close(fd)
        os.close(self.existing())
    def test_symlink_directory(self):
        (self.root/'build').rmdir(); (self.root/'build').symlink_to('/tmp')
        with self.assertRaises(OSError): self.create()
    def test_image_symlink(self):
        self.private.mkdir(mode=0o700); (self.private/'data.ext4').symlink_to('/dev/null')
        with self.assertRaises(OSError): self.existing()
    def test_hardlink(self):
        os.close(self.create()); os.link(self.private/'data.ext4',self.private/'alias')
        with self.assertRaises(ValueError): self.existing()
    def test_bad_file_mode(self):
        os.close(self.create()); (self.private/'data.ext4').chmod(0o644)
        with self.assertRaises(ValueError): self.existing()
    def test_bad_directory_mode(self):
        os.close(self.create()); self.private.chmod(0o755)
        with self.assertRaises(ValueError): self.existing()
    def test_wrong_size(self):
        os.close(self.create()); (self.private/'data.ext4').write_bytes(b'x')
        with self.assertRaises(ValueError): self.existing()
    def test_non_regular(self):
        self.private.mkdir(mode=0o700); os.mkfifo(self.private/'data.ext4',0o600)
        with self.assertRaises(ValueError): self.existing()
    def test_noncanonical(self):
        with self.assertRaises(ValueError): image.open_image(self.root/'..'/self.root.name,True)
    def test_unowned(self):
        with patch.object(image.os,'getuid',return_value=os.getuid()+1):
            with self.assertRaises(ValueError): self.create()
    def test_descriptor_attachment(self):
        args=image.attach(42); file=json.loads(args[1])
        self.assertEqual(file['filename'],'/proc/self/fd/42')
        self.assertFalse(file['cache']['no-flush'])
        self.assertIn('serial=roko-private-files',args[-1])

class SourceTests(unittest.TestCase):
    def test_real_module_closure(self):
        _,_,_,modules,order,_=build.inputs()
        self.assertEqual(set(modules),{'virtio_blk','crc32c_generic','jbd2','crc16','mbcache','ext4'})
        for name,record in modules.items():
            for dependency in record['depends']: self.assertLess(order.index(dependency),order.index(name))
    def test_guest_scope(self):
        init=(build.HERE/'init.sh').read_text()
        self.assertIn('ro,noload,nodev,nosuid,noexec',init)
        self.assertIn('/sys/block/vda/serial',init)
        self.assertNotIn('mkfs',init)
        self.assertIn('umount /data',init)

class FormatterTests(unittest.TestCase):
    def test_rejects_unknown_tool_without_access(self):
        import formatter
        with self.assertRaises(ValueError): formatter.execute('sh',-1)
    def test_rejects_format_mode_confusion(self):
        import formatter
        with self.assertRaises(ValueError): formatter.execute('mke2fs',-1)
        with self.assertRaises(ValueError): formatter.execute('e2fsck',-1,format_image=True)

if __name__=='__main__': unittest.main()
