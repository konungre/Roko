#!/usr/bin/env python3
"""Separate deterministic virtual-KMS probe. No VM without explicit --run."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / 'boot'
OUT = ROOT / 'build/graphics-probe'


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, BOOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = load_module('graphics_archive', 'build.py')
v = load_module('graphics_vm', 'test_vm.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dependency_order(modules):
    result, active = [], set()

    def visit(name):
        if name in active:
            raise ValueError('Module dependency cycle')
        if name in result:
            return
        if name not in modules:
            raise ValueError('Missing module dependency: ' + name)
        active.add(name)
        for dep in modules[name]['depends']:
            visit(dep)
        active.remove(name)
        result.append(name)

    for name in modules:
        visit(name)
    return result


def inputs():
    plan = json.loads((BOOT / 'cosmic-runtime-plan.json').read_text())
    lock = json.loads((BOOT / 'tooling-files.lock.json').read_text())['files']
    assets = json.loads((BOOT / 'boot-assets.lock.json').read_text())
    base = BOOT / 'tooling/root'
    sources = {}

    def verified(path, expected):
        path = Path(path)
        rel = path.relative_to(base).as_posix()
        record = lock.get(rel, {})
        data = path.read_bytes()
        if (path.is_symlink() or record.get('kind') != 'file'
                or digest(data) != expected or expected != record.get('sha256')
                or stat.S_IMODE(path.stat().st_mode) != record.get('mode')):
            raise ValueError('Pinned source mismatch: ' + rel)
        sources[str(path.relative_to(ROOT))] = expected
        return data

    kernel = plan['kernel']
    verified(ROOT / kernel['config']['path'], kernel['config']['sha256'])
    busybox = verified(assets['busybox']['path'], assets['busybox']['sha256'])
    b.check_elf(busybox)
    modules = kernel['module_closure']
    order = dependency_order(modules)
    data = {}
    for name in order:
        record = modules[name]
        compressed = verified(ROOT / record['path'], record['sha256'])
        expanded = lzma.decompress(compressed)
        if digest(expanded) != record['decompressed_sha256']:
            raise ValueError('Decompressed module mismatch: ' + name)
        match = re.search(rb'\x00depends=([^\x00]*)', expanded)
        deps = match[1].decode().split(',') if match and match[1] else []
        if deps != record['depends']:
            raise ValueError('Module dependencies differ: ' + name)
        data[name] = expanded
    for record in plan['qemu']['available_modules']:
        verified(ROOT / record['path'], record['sha256'])
    for name in ('qemu', 'kernel'):
        v.verified_asset(assets[name])
    return assets, kernel['version'], busybox, data, order, sources


def build():
    assets, kernel, busybox, modules, order, sources = inputs()
    init = (BOOT / 'graphics-probe-init.sh').read_bytes()
    build_id = digest(init + json.dumps(sources, sort_keys=True).encode())
    files = {}

    def put(name, data, mode, major=0, minor=0):
        files[name] = (data, mode, major, minor)

    for name in ('bin', 'dev', 'etc', 'modules', 'proc', 'sys', 'licenses'):
        put(name, b'', stat.S_IFDIR | 0o755)
    put('dev/console', b'', stat.S_IFCHR | 0o600, 5, 1)
    put('bin/busybox', busybox, stat.S_IFREG | 0o755)
    put('bin/sh', b'busybox', stat.S_IFLNK | 0o777)
    put('init', init, stat.S_IFREG | 0o755)
    put('etc/module-order', ('\n'.join(order) + '\n').encode(), stat.S_IFREG | 0o444)
    put('etc/kernel-release', (kernel + '\n').encode(), stat.S_IFREG | 0o444)
    put('etc/probe-id', (build_id + '\n').encode(), stat.S_IFREG | 0o444)
    for name, data in modules.items():
        put('modules/' + name + '.ko', data, stat.S_IFREG | 0o444)
    for path in sorted((BOOT / 'licenses').iterdir()):
        if path.is_file():
            put('licenses/' + path.name, path.read_bytes(), stat.S_IFREG | 0o444)
    raw = b''.join(b.entry(name, data, mode, i + 1, major, minor)
                   for i, (name, (data, mode, major, minor)) in enumerate(sorted(files.items())))
    raw += b.entry('TRAILER!!!', b'', 0, len(files) + 1)
    raw += b'\0' * (-len(raw) % 512)
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as handle:
        handle.write(raw)
    archive = stream.getvalue()
    report = {'schema': 1, 'build_id': build_id, 'kernel_release': kernel,
              'sources': sources, 'init_sha256': digest(init),
              'initramfs_sha256': digest(archive), 'initramfs_bytes': len(archive),
              'entries': b.inspect(raw), 'module_order': order,
              'boot_tested': False, 'cosmic_included': False,
              'scope': 'Virtual DRM connector and input-node plumbing only; no rendering or COSMIC.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'probe.cpio.gz').write_bytes(archive)
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def command(assets):
    cmd = v.command(assets['qemu']['path'], assets['kernel']['path'], OUT / 'probe.cpio.gz')
    cmd[cmd.index('-m') + 1] = '512'
    return cmd + ['-device', 'virtio-gpu-pci', '-device', 'virtio-keyboard-pci',
                  '-device', 'virtio-mouse-pci']


def passed(log, build_id, kernel, returncode):
    lines = v.output_lines(log)
    cards = [re.fullmatch(r'ROKO_GRAPHICS_CARD (card\d+) (\d+):(\d+) virtio_gpu', x) for x in lines]
    cards = [m for m in cards if m]
    connector = any(re.fullmatch(r'ROKO_GRAPHICS_CONNECTOR ' + re.escape(c[1]) +
                                r'-[^ ]+ connected \d+x\d+', x)
                    for c in cards for x in lines)
    events = {m[1] for x in lines if (m := re.fullmatch(r'ROKO_GRAPHICS_INPUT (event\d+) .*?[Vv]irtio.*', x))}
    return (returncode == 0 and 'ROKO_GRAPHICS_FAILED' not in log
            and 'ROKO_GRAPHICS_BUILD ' + build_id in lines
            and 'ROKO_GRAPHICS_KERNEL ' + kernel in lines
            and bool(cards) and connector and len(events) >= 2
            and 'ROKO_GRAPHICS_PLUMBING_PASSED' in lines
            and 'ROKO_GRAPHICS_POWER_OFF' in lines and 'Power down' in log)


def preflight():
    assets, kernel, _, _, _, sources = inputs()
    manifest = json.loads((OUT / 'manifest.json').read_text())
    archive = (OUT / 'probe.cpio.gz').read_bytes()
    init = (BOOT / 'graphics-probe-init.sh').read_bytes()
    if (digest(archive) != manifest['initramfs_sha256']
            or b.inspect(gzip.decompress(archive)) != manifest['entries']
            or manifest['sources'] != sources or manifest['kernel_release'] != kernel
            or digest(init) != manifest['init_sha256']
            or manifest['entries']['init']['sha256'] != digest(init)
            or manifest['build_id'] != digest(init + json.dumps(sources, sort_keys=True).encode())):
        raise ValueError('Graphics probe artifact is stale or modified; rebuild it')
    return assets, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--build', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.build:
        report = build()
        print(json.dumps({k: report[k] for k in ('build_id', 'initramfs_bytes', 'module_order', 'boot_tested', 'cosmic_included')}, indent=2))
        return 0
    assets, manifest = preflight()
    report = {'scope': 'Virtual KMS/input plumbing, not COSMIC or rendering',
              'boot_tested': False, 'passed': False, 'command': command(assets),
              'build_id': manifest['build_id'], 'initramfs_sha256': manifest['initramfs_sha256'],
              'kernel_sha256': assets['kernel']['sha256'], 'timeout_seconds': 60,
              'network_enabled': False, 'host_disks_attached': False}
    if args.run:
        integrity = load_module('graphics_integrity', 'verify-tooling.py').verify()
        if not integrity['success']:
            raise ValueError('Tooling integrity failed: ' + str(integrity['errors']))
        try:
            result = subprocess.run(command(assets), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            output, code = result.stdout, result.returncode
            report['timed_out'] = False
        except subprocess.TimeoutExpired as exc:
            output, code = exc.stdout or b'', None
            report['timed_out'] = True
        log = output.decode(errors='replace')
        report.update(boot_tested=True, qemu_returncode=code,
                      passed=passed(log, manifest['build_id'], manifest['kernel_release'], code))
        (ROOT / 'results').mkdir(exist_ok=True)
        (ROOT / 'results/graphics-probe-serial.txt').write_text(log)
        (ROOT / 'results/graphics-probe-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if not args.run or report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
