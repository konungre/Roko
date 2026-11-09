import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "session"))
import foundation_state as state
import state_image
import derive_session as capsule

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.path_patch = patch.object(state, "STATE", self.root)
        self.path_patch.start(); self.addCleanup(self.path_patch.stop)

    def checkpoint(self, phase):
        with patch.object(state, "phase", return_value=phase):
            state.user_checkpoint()

    @unittest.skipUnless(os.getuid() == 1000 and os.getgid() == 1000, "Requires UID/GID1000 fixture owner")
    def test_nonroot_write_reopen(self):
        self.checkpoint("write")
        original = (self.root / state.NAME).read_bytes()
        self.checkpoint("read")
        self.assertEqual(original, state.RAW)
        self.assertEqual((self.root / state.NAME).read_bytes(), original)

    @unittest.skipUnless(os.getuid() == 1000 and os.getgid() == 1000, "Requires UID/GID1000 fixture owner")
    def test_write_never_overwrites(self):
        self.checkpoint("write")
        with self.assertRaises(FileExistsError): self.checkpoint("write")

    def test_root_writer_rejected(self):
        with patch.object(state.os, "getresuid", return_value=(0,0,0)):
            with self.assertRaises(ValueError): self.checkpoint("write")
        self.assertFalse((self.root / state.NAME).exists())

    def test_host_mount_refused(self):
        with self.assertRaises(ValueError): state.prepare()

    @unittest.skipUnless(os.getuid() == 1000 and os.getgid() == 1000, "Requires UID/GID1000 fixture owner")
    def test_symlink_not_followed(self):
        target = self.root / "other"
        target.write_bytes(state.RAW)
        (self.root / state.NAME).symlink_to(target)
        with self.assertRaises(OSError): self.checkpoint("read")

    @unittest.skipUnless(os.getuid() == 1000 and os.getgid() == 1000, "Requires UID/GID1000 fixture owner")
    def test_wrong_content_mode_and_links(self):
        self.checkpoint("write")
        target = self.root / state.NAME
        target.write_bytes(b"changed")
        with self.assertRaises(ValueError): self.checkpoint("read")
        target.write_bytes(state.RAW); target.chmod(0o644)
        with self.assertRaises(ValueError): self.checkpoint("read")
        target.chmod(0o600); os.link(target, self.root / "alias")
        with self.assertRaises(ValueError): self.checkpoint("read")

class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def test_size_mode_and_exclusive_lock(self):
        fd = state_image.open_image(self.root, create=True)
        try:
            self.assertEqual(os.fstat(fd).st_size, state_image.SIZE)
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
            with self.assertRaises(BlockingIOError): state_image.open_image(self.root)
        finally: os.close(fd)
        fd = state_image.open_image(self.root); os.close(fd)

    def test_create_preserves_existing(self):
        (self.root / "state.raw").write_bytes(b"old")
        with self.assertRaises(FileExistsError): state_image.open_image(self.root, create=True)
        self.assertEqual((self.root / "state.raw").read_bytes(), b"old")

    def test_symlink_and_hardlink_refused(self):
        target = self.root / "original"
        target.write_bytes(b"data"); target.chmod(0o600)
        path = self.root / "state.raw"
        path.symlink_to(target)
        with self.assertRaises(OSError): state_image.open_image(self.root)
        path.unlink(); os.link(target, path)
        with self.assertRaises(ValueError): state_image.open_image(self.root)

    def test_nonprivate_directory(self):
        self.root.chmod(0o755)
        with self.assertRaises(ValueError): state_image.open_image(self.root, create=True)

class CapsuleTests(unittest.TestCase):
    def archive(self, name="a", data=b"payload"):
        fields = [1, stat.S_IFREG|0o444,0,0,1,0,len(data),0,0,0,0,0,0]
        return capsule.encode(name,fields,data)+capsule.encode("TRAILER!!!",[0]*13,b"")

    def test_archive_roundtrip(self):
        rows = list(capsule.records(self.archive()))
        self.assertEqual(rows[0][0],"a")
        self.assertEqual(rows[0][2],b"payload")

    def test_traversal_and_truncation(self):
        for raw in (self.archive("../bad"),self.archive("/bad"),self.archive()[:115]):
            with self.assertRaises(ValueError): list(capsule.records(raw))

    def test_anchor_fail_closed(self):
        for value in (b"none", b"twice twice"):
            with self.assertRaises(ValueError): capsule.replace_once(value,"twice","new")

if __name__ == "__main__": unittest.main()
