#!/usr/bin/env python3
"""Preflight by default. --run boots TCG, QMP over pipes; never opens a host listener."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import re
import tempfile
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build/cosmic-guest'
RESULT = ROOT / 'results/cosmic-guest'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def digest(data):
    return hashlib.sha256(data).hexdigest()

def preserve_previous(result, attempts):
    """Move a complete prior attempt without deleting or overwriting any evidence."""
    if result.is_symlink():
        raise ValueError('Latest results must not be a symlink')
    archived = None
    if result.exists() and any(result.iterdir()):
        attempts.mkdir(parents=True, exist_ok=True)
        slot = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%dT%H%M%SZ-', time.gmtime()), dir=attempts))
        archived = slot / 'evidence'
        result.rename(archived)
    result.mkdir(parents=True, exist_ok=True)
    return archived


def has_frame(log, state):
    if state not in (0, 1):
        return False
    pattern = rf'ROKO_WAYLAND_FRAME count=[1-9][0-9]* state={state} time=[0-9]+'
    return any(re.fullmatch(pattern, line) for line in log.splitlines())


def preflight():
    g = module('cosmic_graphics_runner', ROOT / 'boot/graphics_probe.py')
    assets, kernel, _, _, _, sources = g.inputs()
    manifest = json.loads((OUT / 'manifest.json').read_text())
    data = (OUT / 'cosmic.cpio.gz').read_bytes()
    if digest(data) != manifest['initramfs_sha256'] or g.b.inspect(gzip.decompress(data)) != manifest['entries']:
        raise ValueError('Guest archive is changed or malformed')
    if manifest['graphics_sources'] != sources or manifest['kernel_release'] != kernel:
        raise ValueError('Graphics inputs changed')
    for name, expected in manifest['scripts'].items():
        if digest((HERE / name).read_bytes()) != expected:
            raise ValueError('Guest script changed; rebuild: ' + name)
    command = g.v.command(assets['qemu']['path'], assets['kernel']['path'], OUT / 'cosmic.cpio.gz')
    command[command.index('-m') + 1] = '2048'
    command[command.index('-serial') + 1] = 'file:' + str(RESULT / 'serial.txt')
    command += ['-qmp', 'stdio', '-device', 'virtio-gpu-pci', '-device', 'virtio-keyboard-pci',
                '-device', 'virtio-mouse-pci']
    return g, manifest, command

class QMP:
    def __init__(self, proc):
        self.proc = proc
        self.buffer = b''
        self.counter = 0
        self.responses = []
        self.greeting = False
    def poll(self, wait=0):
        if select.select([self.proc.stdout], [], [], wait)[0]:
            data = os.read(self.proc.stdout.fileno(), 65536)
            if data:
                self.buffer += data
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line.strip():
                    obj = json.loads(line)
                    self.responses.append(obj)
                    if 'QMP' in obj:
                        self.greeting = True
    def call(self, command, arguments=None):
        self.counter += 1
        request = {'execute': command, 'id': self.counter}
        if arguments is not None:
            request['arguments'] = arguments
        self.proc.stdin.write(json.dumps(request).encode() + b'\n')
        self.proc.stdin.flush()
        end = time.monotonic() + 5
        while time.monotonic() < end:
            self.poll(.1)
            for response in self.responses:
                if response.get('id') == self.counter:
                    if 'error' in response:
                        raise ValueError('QMP failed: ' + str(response))
                    return response
        raise TimeoutError('QMP timeout: ' + command)
    def key(self, name):
        self.call('input-send-event', {'events': [
            {'type': 'key', 'data': {'down': True, 'key': {'type': 'qcode', 'data': name}}},
            {'type': 'key', 'data': {'down': False, 'key': {'type': 'qcode', 'data': name}}}]})

def run(g, manifest, command):
    integrity = g.load_module('cosmic_tooling_integrity', 'verify-tooling.py').verify()
    if not integrity['success']:
        raise ValueError('Tooling integrity failed: ' + str(integrity['errors']))
    archived = preserve_previous(RESULT, ROOT / 'results/cosmic-guest-attempts')
    report = {'boot_tested': True, 'passed': False, 'full_desktop': False, 'command': command,
              'initramfs_sha256': manifest['initramfs_sha256'], 'build_id': manifest['build_id'],
              'network_enabled': False, 'host_disks_attached': False, 'timeout_seconds': 150,
              'framebuffer_verified': False, 'input_delivery_verified': False,
              'previous_attempt_archive': str(archived) if archived else None}
    verifier = module('cosmic_pixel_verifier', ROOT / 'desktop/wayland-test-client/verify_capture.py')
    report['pixel_verifier_sha256'] = digest((ROOT / 'desktop/wayland-test-client/verify_capture.py').read_bytes())
    frames = set()
    errors = []
    with (RESULT / 'qemu-stderr.txt').open('wb') as stderr:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        qmp = QMP(proc)
        try:
            end = time.monotonic() + 150
            configured = False
            while time.monotonic() < end and proc.poll() is None:
                qmp.poll(.1)
                if qmp.greeting and not configured:
                    qmp.call('qmp_capabilities')
                    configured = True
                log = (RESULT / 'serial.txt').read_text(errors='replace') if (RESULT / 'serial.txt').exists() else ''
                for state in (0, 1):
                    if configured and state not in frames and has_frame(log, state):
                        # Frame callbacks can precede mapped scanout/animations under TCG.
                        # Retry briefly, retaining every capture; never relax pixel equality.
                        capture_end = time.monotonic() + 6
                        attempt = 0
                        while True:
                            time.sleep(.5)
                            path = RESULT / f'frame-{state}-attempt-{attempt}.ppm'
                            qmp.call('screendump', {'filename': str(path)})
                            if not path.is_file():
                                raise ValueError('QMP screendump produced no file')
                            data = path.read_bytes()
                            try:
                                pixels = verifier.locate(data, state)
                            except ValueError:
                                if time.monotonic() >= capture_end:
                                    raise
                                attempt += 1
                                continue
                            (RESULT / f'frame-{state}.ppm').write_bytes(data)
                            report[f'frame_{state}_sha256'] = digest(data)
                            report[f'frame_{state}_pixels'] = pixels
                            report[f'frame_{state}_capture_attempts'] = attempt + 1
                            break
                        frames.add(state)
                        qmp.key('spc' if state == 0 else 'q')
            if proc.poll() is None:
                errors.append('VM exceeded 150 second bound')
        except (ValueError, TimeoutError, OSError) as exc:
            errors.append(str(exc))
        finally:
            # Ask the trusted client to exit first so COSMIC can restore its seat.
            if proc.poll() is None and configured:
                try:
                    qmp.key('q')
                    proc.wait(timeout=5)
                except (ValueError, TimeoutError, OSError, subprocess.TimeoutExpired):
                    pass
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            report['qemu_returncode'] = proc.returncode
            (RESULT / 'qmp.json').write_text(json.dumps(qmp.responses, indent=2) + '\n')
    log = (RESULT / 'serial.txt').read_text(errors='replace') if (RESULT / 'serial.txt').exists() else ''
    report['input_delivery_verified'] = 'ROKO_WAYLAND_INPUT source=space state=1' in log.splitlines() and frames == {0, 1}
    required = ['ROKO_COSMIC_BUILD ' + manifest['build_id'], 'ROKO_COSMIC_SERVICES_READY',
                'ROKO_COSMIC_EXIT 0', 'ROKO_COSMIC_POWER_OFF', 'Power down']
    report['lifecycle_passed'] = all(marker in log for marker in required) and 'ROKO_COSMIC_FAILED' not in log and proc.returncode == 0
    report['errors'] = errors
    report['framebuffer_verified'] = all(f'frame_{s}_pixels' in report for s in (0, 1))
    report['passed'] = report['lifecycle_passed'] and report['input_delivery_verified'] and report['framebuffer_verified'] and not errors
    report['captures'] = sorted(frames)
    (RESULT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    g, manifest, command = preflight()
    if args.run:
        report = run(g, manifest, command)
    else:
        report = {'boot_tested': False, 'command': command, 'build_id': manifest['build_id']}
    print(json.dumps(report, indent=2))
    if args.run:
        raise SystemExit(0 if report['passed'] else 1)
