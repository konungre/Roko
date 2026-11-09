import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_probe
import probe_gate


@unittest.skipUnless(shutil.which("gcc"), "Requires a real x86-64 GCC toolchain")
class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.first = cls.root / "first"
        cls.second = cls.root / "second"
        cls.a = build_probe.build(cls.first)
        cls.b = build_probe.build(cls.second)

    def test_real_compile_is_reproducible(self):
        self.assertEqual(self.a, self.b)
        self.assertEqual((self.first / "initramfs.cpio.gz").read_bytes(), (self.second / "initramfs.cpio.gz").read_bytes())

    def test_host_execution_refuses_before_privilege_operations(self):
        result = subprocess.run([str(self.first / "init")], capture_output=True, timeout=2)
        self.assertEqual(result.returncode, 77)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"ROKO_PROBE_REFUSED_NOT_PID1\n")

    def test_archive_closure(self):
        entries = build_probe.baseline.inspect(gzip.decompress((self.first / "initramfs.cpio.gz").read_bytes()))
        self.assertEqual(set(entries), {"dev", "dev/console", "etc", "etc/roko-profile.json", "init", "proc", "sys"})
        self.assertEqual(entries["init"]["sha256"], self.a["init_sha256"])
        self.assertEqual(entries["dev/console"]["rdevmajor"], 5)
        self.assertEqual(entries["dev/console"]["rdevminor"], 1)
        self.assertFalse(self.a["boot_tested"])
        self.assertFalse(self.a["nonroot_guest_tested"])

    def test_existing_directory_preserved(self):
        with self.assertRaises(FileExistsError):
            build_probe.build(self.first)
        self.assertEqual(json.loads((self.first / "manifest.json").read_text()), self.a)

    def test_missing_compiler_creates_no_output(self):
        output = self.root / "missing-compiler"
        with self.assertRaises(ValueError):
            build_probe.build(output, "roko-nonexistent-compiler")
        self.assertFalse(output.exists())

    def test_preflight_missing_runtime_never_runs(self):
        lock = self.root / "assets.json"
        lock.write_text(json.dumps({"kernel": {"path": "/no/roko/kernel", "sha256": "0"*64}, "qemu": None}))
        report = probe_gate.preflight(self.first, lock)
        self.assertIsNone(report["command"])
        self.assertEqual(len(report["blockers"]), 3)
        self.assertFalse(report["boot_tested"])

    def test_corrupt_artifact_blocks_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(self.first, root / "probe")
            (root / "probe/initramfs.cpio.gz").write_bytes(b"broken")
            report = probe_gate.preflight(root / "probe", root / "missing.json")
            self.assertIn("Probe artifact mismatch", report["blockers"][0])
            self.assertIsNone(report["command"])


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.id = "a" * 64
        self.lines = ["ROKO_FOUNDATION_ENTERED " + self.id,
                      "ROKO_FOUNDATION_NONROOT uid=1000 gid=1000 groups=0 no_new_privs=1 regain_root=denied",
                      "ROKO_FOUNDATION_COMPLETE " + self.id]

    def check(self, lines, code=0):
        return probe_gate.serial_evidence("\r\n".join(lines), self.id, code)["serial_contract_passed"]

    def test_complete_synthetic_receipt_does_not_claim_execution(self):
        self.assertTrue(self.check(self.lines))
        self.assertFalse(probe_gate.serial_evidence("\n".join(self.lines), self.id, 0)["native_execution_independently_established"])

    def test_missing_duplicate_out_of_order_wrong_id(self):
        for lines in (self.lines[:-1], self.lines + self.lines, list(reversed(self.lines)), [line.replace(self.id, "b"*64) for line in self.lines]):
            self.assertFalse(self.check(lines))

    def test_failures_and_unclean_exit(self):
        self.assertFalse(self.check(self.lines, 1))
        for error in ("ROKO_FOUNDATION_FAILED child", "Kernel panic - not syncing"):
            self.assertFalse(self.check(self.lines + [error]))

    def test_invalid_build_id(self):
        with self.assertRaises(ValueError):
            probe_gate.serial_evidence("", "wrong", 0)


if __name__ == "__main__":
    unittest.main()
