#!/usr/bin/env python3
"""Independent Mesa software-device pbuffer gate, not Wayland or scanout proof."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build/egl-probe'
RESULT = ROOT / 'results/egl-probe'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

b = load('egl_builder', HERE / 'build.py')
g = b.graphics()

def build():
    assets, kernel, busybox, _, _, sources = g.inputs()
    lockdata = (b.STAGE / 'debian-files.lock.json').read_bytes()
    c = b.Closure(b.STAGE / 'sysroot', json.loads(lockdata))
    binary = c.external(OUT / 'roko-egl-probe', 'usr/bin/roko-egl-probe')
    for path in ['usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0',
                 'usr/lib/x86_64-linux-gnu/dri/swrast_dri.so',
                 'usr/lib/x86_64-linux-gnu/dri/kms_swrast_dri.so',
                 'usr/share/glvnd/egl_vendor.d/50_mesa.json']:
        c.add(path)
    for path in sorted(c.lock):
        if path.startswith('usr/lib/x86_64-linux-gnu/libgallium-') and path.endswith('.so'):
            c.add(path)
    files = {name: (data, mode, 0, 0) for name, (data, mode) in c.files.items()}
    def put(name, data, mode=0o444):
        files[name] = (data, stat.S_IFREG | mode, 0, 0)
    init = (HERE / 'egl-init.sh').read_bytes()
    identity = {'binary_sha256': binary, 'c_source_sha256': b.sha((HERE / 'egl-probe.c').read_bytes()),
                'init_sha256': b.sha(init), 'sources': sources, 'runtime_sources': c.sources,
                'kernel_release': kernel, 'runtime_lock_sha256': b.sha(lockdata)}
    identity['build_id'] = b.sha(json.dumps(identity, sort_keys=True).encode())
    put('etc/probe-id', (identity['build_id'] + '\n').encode())
    put('init', init, 0o755)
    put('bin/busybox', busybox, 0o755)
    files['bin/sh'] = (b'busybox', stat.S_IFLNK | 0o777, 0, 0)
    files['dev/console'] = (b'', stat.S_IFCHR | 0o600, 5, 1)
    for directory in ['proc', 'sys', 'dev', 'run', 'tmp']:
        files[directory] = (b'', stat.S_IFDIR | 0o755, 0, 0)
    for name in list(files):
        for parent in Path(name).parents:
            if str(parent) != '.':
                files.setdefault(str(parent), (b'', stat.S_IFDIR | 0o755, 0, 0))
    raw = b''.join(g.b.entry(name, data, mode, i + 1, major, minor)
                   for i, (name, (data, mode, major, minor)) in enumerate(sorted(files.items())))
    raw += g.b.entry('TRAILER!!!', b'', 0, len(files) + 1)
    raw += b'\0' * (-len(raw) % 512)
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0, compresslevel=1) as target:
        target.write(raw)
    archive = stream.getvalue()
    (OUT / 'egl.cpio.gz').write_bytes(archive)
    report = dict(identity, initramfs_sha256=b.sha(archive), initramfs_bytes=len(archive),
                  entries=g.b.inspect(raw), elf_closure=c.elfs, boot_tested=False,
                  scope='Mesa software EGL device and GLES2 pbuffer pixels only; no compositor, Wayland or scanout')
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

def preflight():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    assets, kernel, _, _, _, sources = g.inputs()
    archive = (OUT / 'egl.cpio.gz').read_bytes()
    if b.sha(archive) != manifest['initramfs_sha256'] or g.b.inspect(gzip.decompress(archive)) != manifest['entries']:
        raise ValueError('EGL archive mismatch')
    if sources != manifest['sources'] or kernel != manifest['kernel_release']:
        raise ValueError('EGL graphics input mismatch')
    if b.sha((HERE / 'egl-init.sh').read_bytes()) != manifest['init_sha256']:
        raise ValueError('EGL init changed; rebuild')
    command = g.v.command(assets['qemu']['path'], assets['kernel']['path'], OUT / 'egl.cpio.gz')
    command[command.index('-m') + 1] = '1024'
    return manifest, command

def passed(log, build_id, code, timed_out=False):
    import re
    lines = log.splitlines()
    markers = ['ROKO_EGL_BUILD ' + build_id, 'ROKO_EGL_PIXELS_PASSED pixels=64 rgba=17,34,51,255',
               'ROKO_EGL_CLEANUP_DONE', 'ROKO_EGL_EXIT 0', 'ROKO_EGL_POWER_OFF']
    software = any(re.fullmatch(r'ROKO_EGL_SOFTWARE_DEVICE index=[0-9]+', line) for line in lines)
    renderer = any(line.startswith('ROKO_EGL_RENDERER llvmpipe (') for line in lines)
    return (code == 0 and not timed_out and all(x in lines for x in markers)
            and software and renderer and 'Power down' in log
            and 'ROKO_EGL_FAILED' not in log and 'ROKO_EGL_GUEST_FAILED' not in log)


def run():
    manifest, command = preflight()
    integrity = g.load_module('egl_integrity', 'verify-tooling.py').verify()
    if not integrity['success']:
        raise ValueError('QEMU/tooling integrity failure')
    runner = load('egl_preserve', HERE / 'run.py')
    archived = runner.preserve_previous(RESULT, ROOT / 'results/egl-probe-attempts')
    timed_out = False
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=60)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        output, code, timed_out = exc.stdout or b'', None, True
    log = output.decode(errors='replace')
    (RESULT / 'serial.txt').write_text(log)
    report = {'boot_tested': True, 'passed': passed(log, manifest['build_id'], code, timed_out), 'timed_out': timed_out, 'qemu_returncode': code,
              'command': command, 'build_id': manifest['build_id'], 'initramfs_sha256': manifest['initramfs_sha256'],
              'previous_attempt_archive': str(archived) if archived else None, 'timeout_seconds': 60,
              'network_enabled': False, 'host_disks_attached': False, 'scope': manifest['scope']}
    (RESULT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--build', action='store_true')
    choice.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.build:
        report = build()
        print(json.dumps({k: report[k] for k in ['build_id', 'initramfs_bytes', 'boot_tested']}, indent=2))
    elif args.run:
        report = run()
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report['passed'] else 1)
    else:
        manifest, command = preflight()
        print(json.dumps({'boot_tested': False, 'build_id': manifest['build_id'], 'command': command}, indent=2))
