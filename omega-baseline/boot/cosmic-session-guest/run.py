#!/usr/bin/env python3
"""Reduced-session UI gate; explicit --run only, no host listening socket."""
import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build/cosmic-session-guest'
RESULT = ROOT / 'results/cosmic-session-guest'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

old = load('immutable_kiosk_runner', ROOT / 'boot/cosmic-guest/run.py')
build = load('session_builder', HERE / 'build.py')
verifier = load('session_pixel_verifier', ROOT / 'desktop/wayland-test-client/verify_capture.py')

def preflight(memory_mib):
    manifest = json.loads((OUT / 'manifest.json').read_text())
    g = build.base.graphics()
    assets, kernel, _, _, _, sources = g.inputs()
    archive = (OUT / 'session.cpio.gz').read_bytes()
    if old.digest(archive) != manifest['initramfs_sha256']:
        raise ValueError('Session archive changed')
    if g.b.inspect(gzip.decompress(archive)) != manifest['entries']:
        raise ValueError('Session archive structure differs from manifest')
    if sources != manifest['graphics_sources'] or kernel != manifest['kernel_release']:
        raise ValueError('Graphics sources changed')
    for name, digest in manifest['scripts'].items():
        if old.digest((HERE / name).read_bytes()) != digest:
            raise ValueError('Session script changed; rebuild: ' + name)
    command = g.v.command(assets['qemu']['path'], assets['kernel']['path'], OUT / 'session.cpio.gz')
    command[command.index('-m') + 1] = str(memory_mib)
    command[command.index('-serial') + 1] = 'file:' + str(RESULT / 'serial.txt')
    command += ['-qmp', 'stdio', '-device', 'virtio-gpu-pci', '-device', 'virtio-keyboard-pci', '-device', 'virtio-tablet-pci']
    return g, manifest, command

class Controls(old.QMP):
    def chord(self, modifier, key):
        self.call('input-send-event', {'events': [
            {'type': 'key', 'data': {'down': True, 'key': {'type': 'qcode', 'data': modifier}}},
            {'type': 'key', 'data': {'down': True, 'key': {'type': 'qcode', 'data': key}}},
            {'type': 'key', 'data': {'down': False, 'key': {'type': 'qcode', 'data': key}}},
            {'type': 'key', 'data': {'down': False, 'key': {'type': 'qcode', 'data': modifier}}}]})
    def text(self, text):
        mapping = {' ': 'spc', '-': 'minus', '/': 'slash', '.': 'dot', '\n': 'ret'}
        for char in text:
            if char not in 'abcdefghijklmnopqrstuvwxyz0123456789' and char not in mapping:
                raise ValueError('Unsupported test keystroke: ' + repr(char))
            self.key(mapping.get(char, char))
            time.sleep(.045)


def read_serial():
    return (RESULT / 'serial.txt').read_text(errors='replace') if (RESULT / 'serial.txt').exists() else ''

def clean_lines(log):
    return re.sub(r'\x1b\[[0-9;]*m', '', log).splitlines()

def process_snapshot(log):
    blocks = log.split('ROKO_SESSION_PROCESS_SNAPSHOT_BEGIN')
    for block in reversed(blocks[1:]):
        if 'ROKO_SESSION_PROCESS_SNAPSHOT_END' not in block:
            continue
        return {m.group(2): m.group(1) for line in block.split('ROKO_SESSION_PROCESS_SNAPSHOT_END')[0].splitlines()
                if (m := re.fullmatch(r'ROKO_SESSION_PROCESS (/proc/[0-9]+) ([a-z0-9-]+)', line))}
    return {}

def input_ready(log, state):
    ready = False
    for line in log.splitlines():
        if line.startswith(('ROKO_WAYLAND_SUBMIT ', 'ROKO_WAYLAND_CONFIGURE ', 'ROKO_WAYLAND_KEYBOARD_ENTER ')):
            ready = False
        elif re.fullmatch(r'ROKO_WAYLAND_INPUT_READY frames=[1-9][0-9]* state=' + str(state), line):
            ready = True
    return ready


def terminal_colors_ready(colors):
    return bool(colors) and sum(max(c) < 70 and max(c)-min(c) < 5 for c in colors) > len(colors)*3//4


def terminal_pixels_ready(data):
    """Only readiness, never final UI proof; the terminal center can be blank."""
    w, h, pixels = verifier.read_ppm(data)
    if w < 640 or h < 480:
        return False
    colors = [tuple(pixels[(y*w+x)*3:(y*w+x)*3+3])
              for y in range(h//3, h*2//3, 8) for x in range(w//3, w*2//3, 8)]
    return terminal_colors_ready(colors)


def terminal_text_ready(data):
    w, h, pixels = verifier.read_ppm(data)
    # Client area below titlebar: a visible shell prompt/banner, not empty chrome.
    count = sum(1 for y in range(h//4, h//2) for x in range(w//8, w*3//4)
                if min(pixels[(y*w+x)*3:(y*w+x)*3+3]) >= 100
                and max(pixels[(y*w+x)*3:(y*w+x)*3+3])-min(pixels[(y*w+x)*3:(y*w+x)*3+3]) < 8)
    return count >= 100


def desktop_pixels_ready(data):
    """Readiness heuristic only. Final report still requires actual UI inspection."""
    width, height, pixels = verifier.read_ppm(data)
    if width < 640 or height < 480:
        return False
    def pixel(x, y):
        offset = (y * width + x) * 3
        return tuple(pixels[offset:offset + 3])
    background = pixel(width // 4, height // 2)
    red, green, blue = background
    # Genuine configured blue background, not the compositor's gray fallback.
    if not (blue > green + 8 and green > red + 8):
        return False
    top = {pixel(x, 12) for x in range(20, width - 20, 10)}
    return any(color != background for color in top)


def run(g, manifest, command):
    integrity = g.load_module('session_tooling_integrity', 'verify-tooling.py').verify()
    if not integrity['success']:
        raise ValueError('Existing tooling integrity failed')
    archived = old.preserve_previous(RESULT, ROOT / 'results/cosmic-session-guest-attempts')
    report = {'boot_tested': True, 'passed': False, 'automated_passed': False,
              'ui_review_required': True, 'full_desktop': False, 'runs_as_root': True,
              'scope': 'Real reduced session, launcher, diagnostic and terminal; no model or autonomy',
              'command': command, 'build_id': manifest['build_id'], 'initramfs_sha256': manifest['initramfs_sha256'],
              'previous_attempt_archive': str(archived) if archived else None,
              'network_enabled': False, 'host_disks_attached': False, 'timeout_seconds': 330,
              'steps': [], 'screenshots': {}}
    errors = []
    with (RESULT / 'qemu-stderr.txt').open('wb') as stderr:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        qmp = Controls(proc)
        deadline = time.monotonic() + 330
        def wait_for(predicate, seconds, reason):
            end = min(deadline, time.monotonic() + seconds)
            while time.monotonic() < end:
                qmp.poll(.15)
                if predicate(read_serial()):
                    return
                if proc.poll() is not None:
                    raise ValueError('VM exited before ' + reason)
            raise TimeoutError('Timed out waiting for ' + reason)
        def capture(name):
            path = RESULT / (name + '.ppm')
            qmp.call('screendump', {'filename': str(path)})
            data = path.read_bytes()
            report['screenshots'][name] = {'path': path.name, 'sha256': old.digest(data)}
            return data
        def launch(query, label):
            # Actual upstream shortcut activates cosmic-launcher. Its real backend
            # searches installed .desktop files; never start the target via a host shell.
            qmp.chord('meta_l', 'slash')
            time.sleep(5)
            capture(label + '-launcher-open')
            qmp.text(query)
            time.sleep(4)
            capture(label + '-launcher-search')
            qmp.key('ret')
            report['steps'].append('launcher query: ' + query)
        try:
            wait_for(lambda _: qmp.greeting, 10, 'QMP greeting')
            qmp.call('qmp_capabilities')
            required = ['cosmic-session', 'cosmic-comp', 'cosmic-settings', 'cosmic-notifica', 'cosmic-panel', 'cosmic-bg']
            wait_for(lambda log: all(x in process_snapshot(log) for x in required), 110, 'real session processes')
            scene_deadline = min(deadline, time.monotonic() + 90)
            scene_attempt = 0
            while True:
                time.sleep(2)
                data = capture('desktop-ready-' + str(scene_attempt))
                if desktop_pixels_ready(data):
                    (RESULT / 'desktop.ppm').write_bytes(data)
                    report['screenshots']['desktop'] = {'path': 'desktop.ppm', 'sha256': old.digest(data)}
                    break
                if time.monotonic() >= scene_deadline:
                    raise TimeoutError('Rendered background/panel readiness not reached')
                scene_attempt += 1
            initial_pids = process_snapshot(read_serial())
            readiness_log = read_serial()
            report['restart_messages_before_ready'] = [line for line in clean_lines(readiness_log) if 'restarting' in line or 'Restarting' in line]
            time.sleep(8)
            report['initial_processes'] = initial_pids
            report['settled_processes'] = process_snapshot(read_serial())
            report['mandatory_processes_stable'] = all(initial_pids.get(x) == report['settled_processes'].get(x) for x in required)
            launch('roko graphics test', 'test')
            wait_for(lambda log: any(line.startswith('ROKO_SESSION_TEST_LAUNCHED ') for line in log.splitlines()), 20, 'desktop-entry application launch')
            report['desktop_entry_launch_verified'] = True
            for state in (0, 1):
                wait_for(lambda log: old.has_frame(log, state), 20, 'client frame ' + str(state))
                if state == 0:
                    # Right-click establishes pointer/keyboard focus without
                    # triggering this diagnostic's left-click state toggle.
                    qmp.call('input-send-event', {'events': [
                        {'type': 'abs', 'data': {'axis': 'x', 'value': 16384}},
                        {'type': 'abs', 'data': {'axis': 'y', 'value': 16384}}]})
                    time.sleep(1)
                    qmp.call('input-send-event', {'events': [
                        {'type': 'btn', 'data': {'down': True, 'button': 'right'}},
                        {'type': 'btn', 'data': {'down': False, 'button': 'right'}}]})
                qmp.call('input-send-event', {'events': [
                    {'type': 'abs', 'data': {'axis': 'x', 'value': 0}},
                    {'type': 'abs', 'data': {'axis': 'y', 'value': 0}}]})
                end = time.monotonic() + 15
                attempt = 0
                while True:
                    time.sleep(.5)
                    data = capture(f'frame-{state}-attempt-{attempt}')
                    try:
                        match = verifier.locate(data, state)
                    except ValueError:
                        if time.monotonic() >= end:
                            raise
                        attempt += 1
                        continue
                    (RESULT / f'frame-{state}.ppm').write_bytes(data)
                    report[f'frame_{state}_pixels'] = match
                    break
                if state == 0:
                    # Launcher-spawned clients may not receive keyboard focus.
                    # Click the real diagnostic's center using the virtual tablet;
                    # its supported left-click action both focuses and toggles it.
                    qmp.call('input-send-event', {'events': [
                        {'type': 'abs', 'data': {'axis': 'x', 'value': 16384}},
                        {'type': 'abs', 'data': {'axis': 'y', 'value': 16384}}]})
                    wait_for(lambda log: input_ready(log, 0), 20, 'latest diagnostic input-ready callback')
                    qmp.call('input-send-event', {'events': [
                        {'type': 'btn', 'data': {'down': True, 'button': 'left'}},
                        {'type': 'btn', 'data': {'down': False, 'button': 'left'}}]})
                    # COSMIC consumes the activation click on an unfocused
                    # window. Wait for explicit keyboard focus and its new frame,
                    # then issue one Space only if the click did not toggle.
                    wait_for(lambda log: log.rfind('ROKO_WAYLAND_KEYBOARD_ENTER ') > log.rfind('ROKO_WAYLAND_KEYBOARD_LEAVE '),
                             20, 'diagnostic keyboard focus after activation click')
                    wait_for(lambda log: input_ready(log, 0) or 'ROKO_WAYLAND_INPUT source=left-click state=1' in log.splitlines(),
                             20, 'focused diagnostic input readiness')
                    if 'ROKO_WAYLAND_INPUT source=left-click state=1' not in read_serial().splitlines():
                        qmp.key('spc')
                    wait_for(lambda log: any(line in log.splitlines() for line in (
                        'ROKO_WAYLAND_INPUT source=left-click state=1',
                        'ROKO_WAYLAND_INPUT source=space state=1')), 10, 'diagnostic accepted input')
                    # Keep the cursor outside the exact tested content.
                    qmp.call('input-send-event', {'events': [
                        {'type': 'abs', 'data': {'axis': 'x', 'value': 0}},
                        {'type': 'abs', 'data': {'axis': 'y', 'value': 0}}]})
            report['input_delivery_verified'] = any(line in read_serial().splitlines() for line in ('ROKO_WAYLAND_INPUT source=left-click state=1', 'ROKO_WAYLAND_INPUT source=space state=1'))
            qmp.key('q')
            wait_for(lambda log: any(re.fullmatch(r'ROKO_WAYLAND_EXIT reason=key frames=[1-9][0-9]* state=1', line) for line in log.splitlines()), 10, 'trusted test exit')
            time.sleep(1)
            launch('roko terminal', 'terminal')
            wait_for(lambda log: 'cosmic-term' in process_snapshot(log), 25, 'real terminal process')
            terminal_end = min(deadline, time.monotonic() + 55)
            terminal_attempt = 0
            while True:
                time.sleep(2)
                data = capture('terminal-ready-' + str(terminal_attempt))
                if terminal_pixels_ready(data) and terminal_text_ready(data) and 'ROKO_TERMINAL_SHELL_READY ' in read_serial():
                    break
                if time.monotonic() >= terminal_end:
                    raise TimeoutError('Real terminal window not visibly ready')
                terminal_attempt += 1
            qmp.call('input-send-event', {'events': [
                {'type': 'abs', 'data': {'axis': 'x', 'value': 16384}},
                {'type': 'abs', 'data': {'axis': 'y', 'value': 16384}}]})
            qmp.call('input-send-event', {'events': [
                {'type': 'btn', 'data': {'down': True, 'button': 'left'}},
                {'type': 'btn', 'data': {'down': False, 'button': 'left'}}]})
            time.sleep(3)
            qmp.text('roko-terminal-check\n')
            wait_for(lambda log: 'ROKO_TERMINAL_INPUT_OK' in log.splitlines(), 25, 'real terminal typed command')
            report['terminal_input_verified'] = True
            time.sleep(1)
            capture('terminal-marker')
            report['final_processes'] = process_snapshot(read_serial())
            report['mandatory_processes_stable'] = report['mandatory_processes_stable'] and all(initial_pids.get(x) == report['final_processes'].get(x) for x in required)
            qmp.text('roko-session-finish\n')
            wait_for(lambda log: 'ROKO_SESSION_EXIT 0' in log.splitlines(), 20, 'real session exit')
            proc.wait(timeout=10)
        except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
        finally:
            if proc.poll() is None and qmp.greeting:
                try:
                    capture('last-before-stop')
                except (OSError, ValueError, TimeoutError):
                    pass
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            (RESULT / 'qmp.json').write_text(json.dumps(qmp.responses, indent=2) + '\n')
    log = read_serial()
    report['qemu_returncode'] = proc.returncode
    report['errors'] = errors
    report['restart_messages'] = [line for line in clean_lines(log) if 'Restarting' in line or 'restarting' in line]
    report['restart_messages_after_ready'] = report['restart_messages'][len(report.get('restart_messages_before_ready', [])):]
    report['session_interface_exit_verified'] = 'ROKO_SESSION_EXIT_REQUEST' in log.splitlines() and 'EXITING: session exited by request' in log
    report['lifecycle_passed'] = (proc.returncode == 0 and 'ROKO_SESSION_EXIT 0' in log.splitlines()
                                  and 'ROKO_SESSION_POWER_OFF' in log.splitlines() and 'Power down' in log
                                  and 'ROKO_SESSION_FAILED' not in log)
    report['automated_passed'] = (not errors and report.get('mandatory_processes_stable', False)
        and not report['restart_messages_after_ready'] and report.get('desktop_entry_launch_verified', False)
        and all(f'frame_{s}_pixels' in report for s in (0, 1)) and report.get('input_delivery_verified', False)
        and report.get('terminal_input_verified', False) and report['session_interface_exit_verified'] and report['lifecycle_passed'])
    # Visible panel/background/launcher/terminal must still be inspected as real UI.
    (RESULT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--memory-mib', type=int, choices=[2048, 3072, 4096], default=4096)
    args = parser.parse_args()
    g, manifest, command = preflight(args.memory_mib)
    report = run(g, manifest, command) if args.run else {'boot_tested': False, 'command': command, 'build_id': manifest['build_id']}
    print(json.dumps(report, indent=2))
    if args.run:
        raise SystemExit(0 if report['automated_passed'] else 1)
