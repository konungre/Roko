#!/usr/bin/env python3
"""Light offline tests. Never starts a desktop component, VM, or build."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('session_runner_test', HERE / 'run.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class Tests(unittest.TestCase):
    def test_init_refuses_host(self):
        self.assertEqual(subprocess.run(['sh', str(HERE / 'init.sh')]).returncode, 90)

    def test_only_complete_process_snapshots(self):
        log = ('ROKO_SESSION_PROCESS_SNAPSHOT_BEGIN\n'
               'ROKO_SESSION_PROCESS /proc/12 cosmic-panel\n'
               'ROKO_SESSION_PROCESS_SNAPSHOT_END\n'
               'ROKO_SESSION_PROCESS_SNAPSHOT_BEGIN\n'
               'ROKO_SESSION_PROCESS /proc/14 cosmic-panel\n')
        self.assertEqual(r.process_snapshot(log), {'cosmic-panel': '/proc/12'})
        self.assertEqual(r.process_snapshot(log + 'ROKO_SESSION_PROCESS_SNAPSHOT_END'), {'cosmic-panel': '/proc/14'})

    def test_no_kiosk_or_fake_session(self):
        init = (HERE / 'init.sh').read_text()
        self.assertIn('/usr/bin/cosmic-session cosmic-comp --no-xwayland', init)
        self.assertNotIn('/usr/bin/roko-wayland-client', init)
        self.assertNotIn('cosmic-panel &', init)
        self.assertIn('com.system76.CosmicSession.Exit', (HERE / 'roko-session-finish.sh').read_text())

    def test_desktop_readiness_rejects_blank(self):
        width, height = 640, 480
        header = f'P6\n{width} {height}\n255\n'.encode()
        blank = bytes((40, 42, 43)) * width * height
        self.assertFalse(r.desktop_pixels_ready(header + blank))
        blue = bytes((20, 40, 71)) * width * height
        self.assertFalse(r.desktop_pixels_ready(header + blue))
        panel = bytes((30, 30, 30)) * width * 24
        self.assertTrue(r.desktop_pixels_ready(header + panel + blue[len(panel):]))

    def test_click_focus_is_acknowledged_without_blind_retries(self):
        source = (HERE / 'run.py').read_text()
        self.assertIn("'virtio-tablet-pci'", source)
        self.assertIn('ROKO_WAYLAND_INPUT source=left-click state=1', source)
        self.assertIn("'value': 16384", source)
        self.assertIn("'value': 0", source)
        self.assertNotIn('input_end =', source)
        focus = source.index("'down': True, 'button': 'right'")
        center = source.index("'value': 16384", focus)
        press = source.index("'down': True, 'button': 'left'", center)
        release = source.index("'down': False, 'button': 'left'", press)
        ack = source.index("'diagnostic accepted input'", release)
        remove = source.index("'value': 0", ack)
        self.assertLess(center, press)
        self.assertLess(press, release)
        self.assertLess(release, ack)
        self.assertLess(ack, remove)
        # Capture is inside the state loop; state1 is reached only after removal.
        loop = source.index('for state in (0, 1):')
        capture = source.index("capture(f'frame-{state}-attempt-{attempt}')", loop)
        branch = source.index('if state == 0:', capture)
        self.assertLess(focus, capture)
        self.assertLess(source.index("'value': 0", focus), capture)
        self.assertLess(branch, center)
        self.assertLess(remove, source.index("report['input_delivery_verified']", remove))

    def test_ready_is_invalidated_by_new_work(self):
        ready = 'ROKO_WAYLAND_INPUT_READY frames=2 state=0\n'
        self.assertTrue(r.input_ready(ready, 0))
        self.assertFalse(r.input_ready(ready, 1))
        self.assertFalse(r.input_ready(ready + 'ROKO_WAYLAND_SUBMIT state=0\n', 0))
        self.assertFalse(r.input_ready(ready + 'ROKO_WAYLAND_CONFIGURE width=1280 height=800 fullscreen=1\n', 0))
        self.assertTrue(r.input_ready(ready + 'ROKO_WAYLAND_SUBMIT state=0\n' + ready, 0))

    def test_terminal_blank_center_is_valid_readiness(self):
        header = b'P6\n640 480\n255\n'
        self.assertTrue(r.terminal_pixels_ready(header + bytes((27,27,27))*640*480))
        self.assertFalse(r.terminal_pixels_ready(header + bytes((20,41,71))*640*480))

    def test_actual_terminal_and_desktop_sample_regression(self):
        fixtures = json.loads((HERE / 'terminal-readiness-fixtures.json').read_text())
        for fixture in fixtures.values():
            if 'center_sample_histogram' not in fixture:
                self.assertFalse(fixture['client_text_ready'])
                continue
            self.assertEqual(fixture['client_text_ready'], fixture['expected_ready'])
            colors = [tuple(c) for c,n in fixture['center_sample_histogram'] for _ in range(n)]
            self.assertEqual(r.terminal_colors_ready(colors), fixture['expected_ready'])
            self.assertEqual(len(fixture['sha256']), 64)

    def test_safe_keyboard_text(self):
        obj = object.__new__(r.Controls)
        sent = []
        obj.key = sent.append
        old_sleep = r.time.sleep
        r.time.sleep = lambda _: None
        try:
            obj.text('roko-terminal-check\n')
            self.assertEqual(sent[-1], 'ret')
            self.assertEqual(sent.count('minus'), 2)
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                obj.text('\x00')
        finally:
            r.time.sleep = old_sleep

    def test_separate_paths_and_strict_oracle(self):
        self.assertEqual(r.OUT.name, 'cosmic-session-guest')
        self.assertEqual(r.RESULT.name, 'cosmic-session-guest')
        self.assertEqual(r.verifier.WIDTH * r.verifier.HEIGHT, 76800)

if __name__ == '__main__':
    unittest.main()
