import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_probe import verify_runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "runtime"
        self.root.mkdir()
        (self.root / "binary").write_bytes(b"synthetic-runtime")
        (self.root / "binary").chmod(0o755)
        (self.root / "link").symlink_to("binary")
        self.files = {"binary": {"kind": "file", "mode": 0o755, "sha256": hashlib.sha256(b"synthetic-runtime").hexdigest()},
                      "link": {"kind": "symlink", "target": "binary"}}
        self.lock = self.base / "lock.json"
        self.save()

    def save(self):
        self.lock.write_text(json.dumps({"files": self.files}))

    def reject(self):
        with self.assertRaises((ValueError, OSError)):
            verify_runtime(self.root, self.lock)

    def test_exact_inventory(self):
        self.assertEqual(verify_runtime(self.root, self.lock)["entries_verified"], 2)

    def test_corruption(self):
        (self.root / "binary").write_bytes(b"corrupt")
        self.reject()

    def test_mode_change(self):
        (self.root / "binary").chmod(0o777)
        self.reject()

    def test_missing(self):
        (self.root / "binary").unlink()
        self.reject()

    def test_unlisted_module(self):
        (self.root / "extra-module.so").write_bytes(b"injected")
        self.reject()

    def test_symlink_target(self):
        (self.root / "link").unlink()
        (self.root / "link").symlink_to("elsewhere")
        self.reject()

    def test_traversal(self):
        self.files["../outside"] = self.files.pop("binary")
        self.save()
        self.reject()

    def test_symlink_parent(self):
        (self.root / "directory").symlink_to(self.base, target_is_directory=True)
        self.files["directory/lock.json"] = self.files["binary"]
        self.save()
        self.reject()

    def test_unknown_kind(self):
        self.files["binary"]["kind"] = "device"
        self.save()
        self.reject()


if __name__ == "__main__":
    unittest.main()
