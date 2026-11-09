import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('hardware', Path(__file__).resolve().parents[1] / 'foundation/hardware_preflight.py')
hardware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardware)


class HardwareTests(unittest.TestCase):
    def test_missing_evidence_remains_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = hardware.collect(root/'proc', root/'sys', 'aarch64')
            self.assertIsNone(report['memory_bytes'])
            self.assertIsNone(report['avx2_on_all_observed_cpus'])
            self.assertFalse(report['x86_64'])
            self.assertEqual(report['qualification'], 'unverified')

    def test_mixed_cpu_flags_and_intel_driver(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root/'proc'
            sys = root/'sys'
            proc.mkdir()
            (proc/'cpuinfo').write_text('flags : sse avx2\n\nflags : sse\n')
            (proc/'meminfo').write_text('MemTotal: 32000000 kB\n')
            device = sys/'bus/pci/devices/0000:00:02.0'
            device.mkdir(parents=True)
            (device/'class').write_text('0x030000')
            (device/'vendor').write_text('0x8086')
            (device/'device').write_text('0x1234')
            (device/'driver').symlink_to('../../../drivers/i915')
            report = hardware.collect(proc, sys, 'x86_64')
            self.assertFalse(report['avx2_on_all_observed_cpus'])
            self.assertTrue(report['intel_display_observed'])
            self.assertEqual(report['display_controllers'][0]['driver'], 'i915')
            self.assertEqual(report['memory_bytes'], 32768000000)
            self.assertEqual(report['qualification'], 'unverified')
