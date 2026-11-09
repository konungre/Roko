import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "inputs"
        self.assets.mkdir()
        self.lock = {"schema": "roko-release-v1", "architecture": "x86_64", "release": "fixture-1", "assets": []}
        for role in ("rootfs", "kernel", "initramfs"):
            data = (role + "-synthetic-fixture").encode()
            (self.assets / role).write_bytes(data)
            self.lock["assets"].append({"name": role, "role": role, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.lock_path = self.root / "lock.json"
        self.output = self.root / "bundle.tar"
        self.save()

    def save(self):
        self.lock_path.write_text(json.dumps(self.lock))

    def build(self, output=None):
        return release.pack(self.lock_path, self.assets, output or self.output)

    def assert_rejected(self):
        with self.assertRaises((ValueError, OSError)):
            self.build()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".roko-release-*")), [])

    def test_reproducible_across_order_mtime_and_permissions(self):
        first = self.build()
        self.lock["assets"].reverse()
        self.save()
        for item in self.assets.iterdir():
            os.utime(item, (12345, 12345))
            item.chmod(0o600)
        second = self.build(self.root / "second.tar")
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertFalse(first["boot_tested"])
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getnames(), ["release.json", "assets/initramfs", "assets/kernel", "assets/rootfs"])
            for member in archive:
                self.assertEqual((member.uid, member.gid, member.mtime, member.mode), (0, 0, 0, 0o444))
                self.assertTrue(member.isfile())
            lock = json.load(archive.extractfile("release.json"))
            for asset in lock["assets"]:
                raw = archive.extractfile("assets/" + asset["name"]).read()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), asset["sha256"])

    def test_hash_mismatch_leaves_no_partial_release(self):
        self.lock["assets"][0]["sha256"] = "0" * 64
        self.save()
        self.assert_rejected()

    def test_existing_checkpoint_not_overwritten(self):
        self.output.write_bytes(b"checkpoint")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"checkpoint")

    def test_publication_race_preserves_existing_checkpoint(self):
        def collision(source, target):
            Path(target).write_bytes(b"other-build")
            raise FileExistsError(target)
        with patch.object(release.os, "link", side_effect=collision):
            with self.assertRaises(FileExistsError):
                self.build()
        self.assertEqual(self.output.read_bytes(), b"other-build")
        self.assertEqual(list(self.root.glob(".roko-release-*")), [])

    def test_missing_asset(self):
        (self.assets / "kernel").unlink()
        self.assert_rejected()

    def test_symlink(self):
        (self.assets / "kernel").unlink()
        (self.assets / "kernel").symlink_to(self.assets / "rootfs")
        self.assert_rejected()

    def test_hardlink(self):
        os.link(self.assets / "kernel", self.root / "alias")
        self.assert_rejected()

    def test_fifo_does_not_block(self):
        (self.assets / "kernel").unlink()
        os.mkfifo(self.assets / "kernel")
        self.assert_rejected()

    def test_directory_asset(self):
        (self.assets / "kernel").unlink()
        (self.assets / "kernel").mkdir()
        self.assert_rejected()

    def test_directory_symlink(self):
        alias = self.root / "alias"
        alias.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaises(ValueError):
            release.pack(self.lock_path, alias, self.output)

    def test_mutation_during_copy(self):
        original = release.CheckedReader.read
        def mutate(reader, size):
            data = original(reader, size)
            with (self.assets / "initramfs").open("ab") as stream:
                stream.write(b"changed")
            return data
        with patch.object(release.CheckedReader, "read", mutate):
            self.assert_rejected()

    def test_invalid_locks(self):
        baseline = copy.deepcopy(self.lock)
        cases = [
            ("name", "../kernel"), ("name", "/kernel"), ("name", "a/b"),
            ("name", "."), ("name", ".."), ("name", "kernel\n"),
            ("bytes", True), ("bytes", 0), ("bytes", -1), ("bytes", release.MAX_ASSET + 1),
            ("sha256", "a" * 63), ("role", "unknown"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.lock = copy.deepcopy(baseline)
                self.lock["assets"][0][key] = value
                self.save()
                self.assert_rejected()

    def test_duplicate_roles_names_and_missing_roles(self):
        baseline = copy.deepcopy(self.lock)
        for field in ("name", "role"):
            self.lock = copy.deepcopy(baseline)
            self.lock["assets"][0][field] = self.lock["assets"][1][field]
            self.save()
            self.assert_rejected()

    def test_duplicate_json_key(self):
        self.lock_path.write_text('{"schema":"a","schema":"b"}')
        self.assert_rejected()

    def test_unknown_field(self):
        self.lock["boot_tested"] = True
        self.save()
        self.assert_rejected()

    def test_oversized_lock(self):
        self.lock_path.write_bytes(b" " * (1024 * 1024 + 1))
        self.assert_rejected()

    def test_wrong_architecture(self):
        self.lock["architecture"] = "aarch64"
        self.save()
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
