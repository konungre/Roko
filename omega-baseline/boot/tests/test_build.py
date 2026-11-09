"""Real compiler and malformed archive regression checks; no VM or privileges."""
import contextlib
import importlib.util
import io
from pathlib import Path
import stat
import subprocess
import struct
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'build.py'
spec = importlib.util.spec_from_file_location('rescue_build', SOURCE)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def archive(name='init', data=b'hello', mode=stat.S_IFREG | 0o755):
    return build.entry(name, data, mode, 1) + build.entry('TRAILER!!!', b'', 0, 2)


class ArchiveTests(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(build.inspect(archive())['init']['bytes'], 5)

    def test_noncanonical_names(self):
        for name in ('', '/init', '../init', 'a/../b', './init', 'a//b', 'a/', 'a\0b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build.entry(name, b'', stat.S_IFREG | 0o644, 1)

    def test_untrusted_paths(self):
        for name in (b'../x', b'/ini', b'./xx', b'a//b', b'a\0xx'):
            raw = archive().replace(b'init\0', name + b'\0', 1)
            with self.subTest(name=name), self.assertRaises(ValueError):
                build.inspect(raw)

    def test_every_truncation(self):
        raw = archive()
        for length in range(len(raw)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                build.inspect(raw[:length])

    def test_duplicate_trailing_and_bad_records(self):
        samples = [archive() + b'payload', archive() + archive(),
                   build.entry('init', b'', stat.S_IFREG | 0o644, 1) + archive(),
                   archive(mode=stat.S_IFDIR | 0o755), archive(mode=0)]
        for raw in samples:
            with self.assertRaises(ValueError):
                build.inspect(raw)

    def test_zero_block_padding(self):
        self.assertIn('init', build.inspect(archive() + bytes(512)))


class RealBuildTests(unittest.TestCase):
    def test_rebuild_and_host_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = [Path(temp) / name for name in ('one', 'two')]
            for output in outputs:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(minimal=True, output=output)
            for name in ('init', 'roko-initramfs.cpio.gz', 'build-manifest.json'):
                self.assertEqual((outputs[0]/name).read_bytes(), (outputs[1]/name).read_bytes())
            executable = (outputs[0]/'init').read_bytes()
            for length in range(64):
                with self.assertRaises(ValueError):
                    build.check_elf(executable[:length])
            for position, fmt, value in ((18, '<H', 3), (32, '<Q', len(executable)), (54, '<H', 0), (56, '<H', 0)):
                damaged = bytearray(executable)
                struct.pack_into(fmt, damaged, position, value)
                with self.assertRaises(ValueError):
                    build.check_elf(damaged)
            result = subprocess.run([str(outputs[0]/'init')], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 77)
            self.assertIn(b'refuses to run outside guest PID 1', result.stderr)


if __name__ == '__main__':
    unittest.main()
