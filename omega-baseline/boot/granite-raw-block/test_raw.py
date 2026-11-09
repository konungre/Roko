import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import raw_transport as transport
import host_fixture
import synthetic
import prepare


class RawTests(unittest.TestCase):
    def setUp(self):
        self.spec = synthetic.specification()

    def record(self):
        return {'name': 'vdb', 'serial': self.spec['serial'], 'sectors': self.spec['capacity_bytes'] // 512,
                'readonly': 1, 'dev': '254:16', 'logical_block_size': 512, 'partitions': [],
                'driver': '/sys/bus/virtio/drivers/virtio_blk', 'subsystem': '/sys/bus/virtio'}

    def test_exact_non_aligned_geometry(self):
        self.assertEqual(self.spec['source_bytes'] % 512, 352)
        self.assertEqual(self.spec['zero_tail_bytes'], 160)
        self.assertEqual(transport.capacity(transport.MODEL_BYTES), 4230976512)
        self.assertEqual(transport.validate_spec(self.spec, False), self.spec)
        for key, wrong in [('source_bytes', True), ('capacity_bytes', 512), ('zero_tail_bytes', 0),
                           ('logical_block_size', 4096), ('transport', 'guess'), ('serial', '../vda')]:
            with self.assertRaises(ValueError):
                transport.validate_spec(dict(self.spec, **{key: wrong}), False)

    def test_production_status_and_fixed_model_are_required(self):
        spec = dict(self.spec, serial='roko-granite-model', source_bytes=transport.MODEL_BYTES,
                    capacity_bytes=transport.capacity(transport.MODEL_BYTES), sha256=transport.MODEL_SHA)
        for status in ('source-only-not-built', 'awaiting-synthetic-proof-and-reviewed-admission'):
            with self.assertRaisesRegex(ValueError, 'awaits synthetic'):
                transport.validate_spec(dict(spec, status=status))
        good = dict(spec, status='raw-model-transport-admitted', reviewed_admission=True,
                    synthetic_receipt_sha256='1' * 64)
        self.assertEqual(transport.validate_spec(good), good)
        for key, wrong in [('serial', 'roko-raw-synthetic'), ('sha256', '0' * 64),
                           ('reviewed_admission', 1), ('synthetic_receipt_sha256', '0' * 64)]:
            with self.assertRaises(ValueError):
                transport.validate_spec(dict(good, **{key: wrong}))

    def test_wrong_readonly_driver_identity_and_partitions_rejected(self):
        self.assertEqual(transport.validate_record(self.record(), self.spec), self.record())
        for key, wrong in [('readonly', 0), ('serial', 'roko-other'), ('sectors', 1), ('name', 'vdb1'),
                           ('partitions', ['vdb1']), ('driver', '/sys/bus/scsi/drivers/sd'),
                           ('subsystem', '/sys/bus/pci'), ('logical_block_size', 4096), ('dev', 'bad')]:
            with self.assertRaises(ValueError):
                transport.validate_record(dict(self.record(), **{key: wrong}), self.spec)

    def test_discovery_requires_unique_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                transport.discover(self.spec, root)
            for name in ['vdb', 'vdc']:
                (root / name).mkdir()
                (root / name / 'serial').write_text(self.spec['serial'])
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                transport.discover(self.spec, root)

    def test_regular_device_descriptor_is_rejected_and_closed(self):
        with tempfile.TemporaryFile() as stream:
            copied = os.dup(stream.fileno())
            with patch.object(transport, 'discover', return_value=self.record()), patch.object(transport.os, 'open', return_value=copied):
                with self.assertRaisesRegex(ValueError, 'does not match sysfs'):
                    transport.admit(self.spec, time.monotonic() + 1, production=False)
            with self.assertRaises(OSError):
                os.fstat(copied)

    def test_prefix_seek_and_mmap_byte_helpers_on_padded_regular_fixture(self):
        # Byte-helper unit test, not evidence of block-device kernel behavior.
        with tempfile.TemporaryFile() as stream:
            stream.write(synthetic.payload() + b'\0' * self.spec['zero_tail_bytes'])
            stream.flush()
            report = transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() + 2, True)
            self.assertTrue(report['mmap_checked'])
            self.assertEqual(report['seek_end'], self.spec['capacity_bytes'])
            with self.assertRaises(TimeoutError):
                transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() - 1)
            os.pwrite(stream.fileno(), b'X', self.spec['source_bytes'])
            with self.assertRaisesRegex(ValueError, 'tail'):
                transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() + 2)
            os.pwrite(stream.fileno(), b'X', 0)
            with self.assertRaisesRegex(ValueError, 'prefix hash'):
                transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() + 2)

    def test_short_source_or_wrong_capacity_rejected(self):
        with tempfile.TemporaryFile() as stream:
            stream.write(synthetic.payload()[:100])
            stream.flush()
            with self.assertRaisesRegex(ValueError, 'Short'):
                transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() + 2)
        with tempfile.TemporaryFile() as stream:
            stream.write(synthetic.payload() + b'\0' * (self.spec['zero_tail_bytes'] + 512))
            stream.flush()
            with self.assertRaisesRegex(ValueError, 'SEEK_END'):
                transport.verify_bytes(stream.fileno(), self.spec, time.monotonic() + 2)

    def test_synthetic_host_fd_readonly_and_explicit_raw_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'synthetic.raw'
            path.write_bytes(synthetic.payload())
            path.chmod(0o444)
            fd, before = host_fixture.open_fixture(root)
            try:
                args = host_fixture.attachment(fd)
                nodes = [json.loads(args[i+1]) for i, x in enumerate(args) if x == '-blockdev']
                self.assertEqual([x['driver'] for x in nodes], ['file', 'raw'])
                self.assertTrue(all(x['read-only'] is True for x in nodes))
                self.assertEqual(nodes[0]['filename'], f'/proc/self/fd/{fd}')
                with self.assertRaises(OSError) as ctx:
                    os.pwrite(fd, b'X', 0)
                self.assertEqual(ctx.exception.errno, errno.EBADF)
                self.assertEqual(host_fixture.verify(fd, before), before)
                # A child can open the live parent's pinned descriptor even when
                # close_fds=True, as used by the separate native supervisor.
                code = 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())'
                result = subprocess.run([sys.executable, '-c', code, f'/proc/{os.getpid()}/fd/{fd}'],
                                        close_fds=True, text=True, capture_output=True, timeout=3, check=True)
                self.assertEqual(result.stdout.strip(), self.spec['sha256'])
            finally:
                os.close(fd)

    def test_symlink_writable_or_wrong_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'synthetic.raw'
            path.write_bytes(synthetic.payload())
            with self.assertRaisesRegex(ValueError, 'exact inert'):
                host_fixture.open_fixture(root)
            path.chmod(0o444)
            other = root / 'other'
            path.rename(other)
            path.symlink_to(other)
            with self.assertRaises(OSError):
                host_fixture.open_fixture(root)

    def test_tiny_source_only_delta_preserves_original_bootstrap(self):
        original = (ROOT / 'boot/disk-root-guest/init.sh').read_bytes()
        entries, report = prepare.tiny_delta()
        init = entries['init'][0]
        self.assertLess(report['delta_payload_bytes'], 2 * 1024**2)
        self.assertFalse(report['fixture_materialized'])
        self.assertFalse(report['model_attached'])
        self.assertIn(b'/run/raw-model-probe/init', init)
        self.assertNotIn(b' /usr/libexec/roko-session-init', init)
        self.assertEqual((ROOT / 'boot/disk-root-guest/init.sh').read_bytes(), original)

    def test_actual_provider_failure_closes_pinned_block(self):
        stage = prepare.OUT / 'opt/roko'
        code = r"""
import importlib.util, sys
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1])
sys.path[:0]=[str(root/'adapters'), str(root/'vendor/guest-python'), str(root/'vendor/PeTTa/repos/Omega/src')]
import granite_guest, providers
p=granite_guest.GraniteGuestProvider(root)
try:p.start()
except ValueError as error:assert 'awaits binary and loader admission' in str(error)
else:raise AssertionError('source stage activated')
assert not p.ready
class Block:
    closed=False
    def close(self):self.closed=True
block=Block()
def fail(provider, verify):
    provider._raw_model=block
    raise ValueError('later loader failure')
with patch.object(granite_guest,'start_runtime',fail):
    try:p.start()
    except ValueError:pass
    else:raise AssertionError('failure hidden')
assert block.closed and p._raw_model is None and not p.ready
assert issubclass(granite_guest.GraniteGuestProvider,providers.LLMProvider)
"""
        subprocess.run([sys.executable, '-c', code, str(stage)], check=True, timeout=5)

    def test_runner_defaults_do_not_materialize_or_launch(self):
        import run_synthetic
        with patch.object(run_synthetic.subprocess, 'Popen', side_effect=AssertionError('VM launch')):
            _, plan = run_synthetic.prepare.tiny_delta()
            self.assertFalse(plan['fixture_materialized'])
        entries, _ = prepare.tiny_delta()
        subprocess.run(['sh', '-n'], input=entries['init'][0], check=True, timeout=3)
        subprocess.run(['sh', '-n'], input=entries['raw-model-probe/init'][0], check=True, timeout=3)

    def test_regular_file_default_is_unchanged_and_raw_stage_is_disabled(self):
        base = ROOT / 'boot/granite-portable/runtime_select.py'
        old = hashlib.sha256(base.read_bytes()).hexdigest()
        original, variant, _, provider = prepare.source_variants()
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), old)
        self.assertIn("'/models/granite-4.0-h-tiny-Q4_K_M.gguf'", original)
        self.assertNotIn('admit_model(root, deadline)', original)
        self.assertIn('admit_model(root, deadline)', variant)
        self.assertIn('block.close()', provider)
        stage = prepare.OUT / 'opt/roko'
        status = json.loads((stage / 'granite-raw-transport.lock.json').read_text())
        with self.assertRaisesRegex(ValueError, 'awaits synthetic'):
            transport.validate_spec(status)


if __name__ == '__main__':
    unittest.main()
