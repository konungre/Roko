#!/usr/bin/env python3
"""Prepare/assemble only the approved fixed cognitive capsule serial harness.

No VM/native process is started here. Assembly is deferred until lane release.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / 'build-src/cognitive-capsule-guest/stage-v4'
OUT = ROOT / 'build-src/cognitive-capsule-guest/harness-v3'
MANIFEST_SHA = '1df0cdcb824e3f542bca8c5760554f72f049e0e338620731e6a485953ddbad42'
ROOT_SHA = '8fa91b7751abae9d16b4022402ac22b85cd308fa67810b809d4ad1f5d42ea03d'
OVERLAY_CAP = 128 * 1024**2
TOTAL_ARTIFACT_CAP = 512 * 1024**2
DISK_RESERVE = 4 * 1024**3


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive = load('cognitive_cpio_functions', ROOT / 'boot/build.py')


def admission():
    return {'version': 1, 'scope': 'single-guest-cognitive-gate',
            'manifest_sha256': MANIFEST_SHA, 'native_execution_reviewed': True}


def frozen():
    raw = (STAGE / 'manifest.json').read_bytes()
    if sha(raw) != MANIFEST_SHA:
        raise ValueError('Reviewed capsule manifest changed')
    manifest = json.loads(raw)
    for name, pin in manifest['files'].items():
        path = STAGE / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != pin['bytes'] or stat.S_IMODE(path.stat().st_mode) != pin['mode'] or sha(path.read_bytes()) != pin['sha256']:
            raise ValueError('Reviewed capsule file changed: ' + name)
    return manifest


def prepare():
    manifest = frozen()
    if shutil.disk_usage(ROOT).free < DISK_RESERVE + 2 * 1024**2:
        raise ValueError('Harness staging would cross disk reserve')
    OUT.mkdir(parents=True, mode=0o700, exist_ok=False)
    files = {'guest_driver.py': (HERE / 'guest_driver.py').read_bytes(),
             'guest_init.sh': (HERE / 'guest_init.sh').read_bytes(),
             'guest-admission.json': (json.dumps(admission(), sort_keys=True) + '\n').encode()}
    for name, data in files.items():
        path = OUT / name
        path.write_bytes(data); path.chmod(0o444)
    plan = {'version': 1, 'status': 'prepared-awaiting-heavy-lane-release',
            'capsule_manifest_sha256': MANIFEST_SHA, 'root_sha256': ROOT_SHA,
            'memory_mib': 2048, 'tcg_cpus': 2, 'graphics_started': False,
            'vm_seconds': 300, 'guest_watchdog_seconds': 240,
            'runner_operating_seconds': 480, 'cleanup_reserved_seconds': 90,
            'overlay_cap_bytes': OVERLAY_CAP, 'total_artifact_cap_bytes': TOTAL_ARTIFACT_CAP,
            'host_available_floor_bytes': 2 * 1024**3, 'host_prelaunch_available_bytes': 5 * 1024**3,
            'qemu_rss_cap_bytes': 3 * 1024**3, 'host_disk_floor_bytes': DISK_RESERVE,
            'model_attached': False, 'network_enabled': False, 'external_actions': False,
            'fixture_order': ['primitive', 'multiply', 'fresh-add', 'data-roundtrip', 'actual-cli'],
            'fault_workers_included': False, 'files': {n: {'sha256': sha(d), 'bytes': len(d)} for n, d in files.items()},
            'recipe_sha256': {p.name: sha(p.read_bytes()) for p in (HERE/'harness.py', HERE/'run_serial.py')},
            'tooling_source_sha256': {'boot/build.py': sha((ROOT/'boot/build.py').read_bytes()),
                                      'boot/disk-root-guest/image.py': sha((ROOT/'boot/disk-root-guest/image.py').read_bytes())},
            'native_execution_performed': False, 'capsule_payload_bytes': manifest['payload_bytes']}
    (OUT / 'harness.lock.json').write_text(json.dumps(plan, indent=2) + '\n')
    (OUT / 'harness.lock.json').chmod(0o444)
    return plan


def validate():
    plan = json.loads((OUT / 'harness.lock.json').read_text())
    if plan['capsule_manifest_sha256'] != MANIFEST_SHA or plan['root_sha256'] != ROOT_SHA:
        raise ValueError('Harness targets changed')
    for name, pin in plan['files'].items():
        path = OUT / name
        data = path.read_bytes()
        if path.is_symlink() or len(data) != pin['bytes'] or sha(data) != pin['sha256']:
            raise ValueError('Frozen harness input changed')
    for name, expected in plan['recipe_sha256'].items():
        if sha((HERE / name).read_bytes()) != expected:
            raise ValueError('Frozen harness recipe changed')
    for name, expected in plan['tooling_source_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('Pinned packaging/root helper changed')
    return plan


def unpack(raw):
    # Validate first, then extract data with the same newc metadata convention.
    archive.inspect(raw)
    offset = 0; result = {}
    while True:
        fields = [int(raw[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        mode, size, length = fields[1], fields[6], fields[11]
        offset += 110; name = raw[offset:offset+length-1].decode()
        offset += length; offset += -offset % 4
        data = raw[offset:offset+size]; offset += size; offset += -offset % 4
        if name == 'TRAILER!!!':
            return result
        result[name] = (data, mode, fields[9], fields[10])


def assemble(out):
    plan = validate(); manifest = frozen()
    bootstrap = ROOT / 'build/disk-root-guest/bootstrap.cpio.gz'
    pin = json.loads((bootstrap.parent / 'bootstrap.json').read_text())
    packed = bootstrap.read_bytes(); raw = gzip.decompress(packed)
    if sha(packed) != pin['initramfs_sha256'] or archive.inspect(raw) != pin['entries']:
        raise ValueError('Original tiny bootstrap changed')
    entries = unpack(raw)
    hook = b'# Move pseudo filesystems, not static root files. switch_root releases bootstrap RAM.\n'
    install = b'''$BB mkdir -m 700 /newroot/run/roko-cognitive-gate || fail cognitive-directory
$BB cp -a /cognitive-seed/. /newroot/run/roko-cognitive-gate/ || fail cognitive-payload
(cd /newroot/run/roko-cognitive-gate && $BB sha256sum -c /cognitive.sha256 >/dev/null) || fail cognitive-integrity
echo ROKO_COGNITIVE_OVERLAY_READY
'''
    init = entries['init'][0]
    target = b'exec /bin/busybox switch_root /newroot /usr/libexec/roko-session-init\n'
    if init.count(hook) != 1 or init.count(target) != 1:
        raise ValueError('Exact root-switch hook changed')
    init = init.replace(hook, install + hook).replace(target, b'exec /bin/busybox switch_root /newroot /bin/sh /run/roko-cognitive-gate/guest_init.sh\n')
    entries['init'] = (init, stat.S_IFREG | 0o755, 0, 0)
    sums = []; overlay_bytes = 0
    def put(name, data, mode=0o444):
        nonlocal overlay_bytes
        overlay_bytes += len(data)
        if overlay_bytes > OVERLAY_CAP:
            raise ValueError('Separate cognitive overlay exceeds128MiB')
        dest = 'cognitive-seed/' + name
        entries[dest] = (data, stat.S_IFREG | mode, 0, 0)
        sums.append(sha(data) + '  ' + name + '\n')
        for parent in Path(dest).parents:
            if str(parent) != '.':
                entries.setdefault(str(parent), (b'', stat.S_IFDIR | 0o700, 0, 0))
    for name, entry in manifest['files'].items():
        put(name, (STAGE / name).read_bytes(), entry['mode'])
    put('manifest.json', (STAGE / 'manifest.json').read_bytes())
    for name in ('guest_driver.py', 'guest_init.sh'):
        put(name, (OUT / name).read_bytes())
    put('admission.json', (OUT / 'guest-admission.json').read_bytes())
    entries['cognitive.sha256'] = (''.join(sums).encode(), stat.S_IFREG | 0o444, 0, 0)
    if shutil.disk_usage(ROOT).free < DISK_RESERVE + 64 * 1024**2:
        raise ValueError('Archive assembly disk reserve insufficient')
    out = Path(out); out.mkdir(mode=0o700, parents=True, exist_ok=False)
    path = out / 'bootstrap.cpio.gz'
    with path.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', filename='', compresslevel=1, mtime=0) as zipped:
        length = 0
        for i, (name, (data, mode, major, minor)) in enumerate(sorted(entries.items())):
            blob = archive.entry(name, data, mode, i + 1, major, minor)
            zipped.write(blob); length += len(blob)
        tail = archive.entry('TRAILER!!!', b'', 0, len(entries) + 1)
        zipped.write(tail); length += len(tail); zipped.write(b'\0' * (-length % 512))
    path.chmod(0o444)
    receipt = {'capsule_manifest_sha256': MANIFEST_SHA, 'harness_lock_sha256': sha((OUT/'harness.lock.json').read_bytes()),
               'initramfs_sha256': sha(path.read_bytes()), 'initramfs_bytes': path.stat().st_size,
               'uncompressed_overlay_bytes': overlay_bytes, 'plan': plan, 'native_execution_performed': False}
    (out / 'assembly.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return path, receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare() if args.prepare else validate(), indent=2))
