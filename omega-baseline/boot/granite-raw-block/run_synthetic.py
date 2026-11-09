#!/usr/bin/env python3
"""Explicit --run gate for one inert raw block, no model or host filesystem export.

Requires a coordinated lane grant outside this script. Default only prints the
source plan. Existing accepted root is opened read-only and never copied.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

import host_fixture
import prepare
import synthetic

ROOT = prepare.ROOT
HERE = Path(__file__).resolve().parent
RESERVE = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive = load('raw_probe_archive', ROOT / 'boot/build.py')
root_image = load('raw_probe_root_image', ROOT / 'boot/disk-root-guest/image.py')


def disk_free():
    info = os.statvfs(ROOT)
    return info.f_bavail * info.f_frsize


def available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise ValueError('Missing host memory admission')


def fd_hash(fd, seconds=120):
    deadline = time.monotonic() + seconds
    digest = hashlib.sha256()
    length = os.fstat(fd).st_size
    offset = 0
    while offset < length:
        if time.monotonic() >= deadline:
            raise TimeoutError('Bounded root hash deadline')
        chunk = os.pread(fd, min(4 * 1024**2, length-offset), offset)
        if not chunk:
            raise ValueError('Short root image')
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def unpack(data):
    expected = archive.inspect(data)
    entries = {}
    offset = 0
    while True:
        fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        offset += 110
        name = data[offset:offset+fields[11]-1].decode()
        offset += fields[11]
        offset += -offset % 4
        value = data[offset:offset+fields[6]]
        offset += fields[6]
        offset += -offset % 4
        if name == 'TRAILER!!!':
            break
        entries[name] = (value, fields[1], fields[9], fields[10])
    if set(entries) != set(expected):
        raise ValueError('Archive extractor mismatch')
    return entries


def assemble(out):
    delta, plan = prepare.tiny_delta()
    base = ROOT / 'build/disk-root-guest/bootstrap.cpio.gz'
    raw = gzip.decompress(base.read_bytes())
    manifest = json.loads((base.parent / 'bootstrap.json').read_text())
    if archive.inspect(raw) != manifest['entries']:
        raise ValueError('Base archive entries changed')
    entries = unpack(raw)
    if set(entries) & set(delta) != {'init'}:
        raise ValueError('Unexpected synthetic delta collision')
    entries.update(delta)
    stream = b''.join(archive.entry(name, value, mode, index+1, major, minor)
                      for index, (name, (value, mode, major, minor)) in enumerate(sorted(entries.items())))
    stream += archive.entry('TRAILER!!!', b'', 0, len(entries)+1)
    stream += b'\0' * (-len(stream) % 512)
    zipped = gzip.compress(stream, compresslevel=1, mtime=0)
    if len(zipped) > 3 * 1024**2:
        raise ValueError('Synthetic bootstrap archive exceeds 3 MiB')
    target = out / 'bootstrap.cpio.gz'
    with target.open('xb') as destination:
        destination.write(zipped)
    target.chmod(0o444)
    plan.update(initramfs_sha256=prepare.sha(zipped), initramfs_bytes=len(zipped),
                assembled=True, entries=archive.inspect(stream))
    fixture = out / 'synthetic.raw'
    with fixture.open('xb') as destination:
        destination.write(synthetic.payload())
        destination.flush()
        os.fsync(destination.fileno())
    fixture.chmod(0o444)
    (out / 'assembly.json').write_text(json.dumps(plan, indent=2) + '\n')
    return target, plan


def command(assets, bootstrap, root_fd, fixture_fd):
    args = [assets['qemu']['path'], '-no-user-config', '-nodefaults', '-machine', 'q35,accel=tcg',
            '-m', '512', '-smp', '1', '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
            '-nic', 'none', '-no-reboot', '-kernel', assets['kernel']['path'], '-initrd', str(bootstrap),
            '-append', 'console=ttyS0 rdinit=/init panic=1']
    args += root_image.attach(root_fd)  # vda, accepted root, O_RDONLY.
    args += host_fixture.attachment(fixture_fd)  # vdb, inert bytes only, O_RDONLY.
    return args


def terminate(proc):
    if proc is not None and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)


def run():
    before_free = disk_free()
    if before_free < RESERVE + 16 * 1024**2 or available() < 3 * 1024**3:
        raise ValueError('Requires 4 GiB free disk plus 16 MiB output allowance and 3 GiB host MemAvailable')
    build_parent = ROOT / 'build/granite-raw-synthetic'
    result_parent = ROOT / 'results/granite-raw-synthetic'
    build_parent.mkdir(mode=0o700, exist_ok=True)
    result_parent.mkdir(mode=0o700, exist_ok=True)
    attempt = 1
    while (build_parent / f'attempt-{attempt}').exists() or (result_parent / f'attempt-{attempt}').exists():
        attempt += 1
    out = build_parent / f'attempt-{attempt}'
    result = result_parent / f'attempt-{attempt}'
    out.mkdir(mode=0o700)
    result.mkdir(mode=0o700)
    report = {'passed': False, 'boot_tested': False, 'model_attached': False, 'model_loaded': False,
              'host_directory_shared': False, 'network_enabled': False, 'memory_mib': 512,
              'tcg_cpus': 1, 'vm_wall_seconds': 120, 'host_rss_cap_bytes': 1536 * 1024**2,
              'host_available_reserve_bytes': 2 * 1024**3, 'free_disk_before': before_free,
              'errors': [], 'result_path': str(result.relative_to(ROOT)), 'fixture_created': False}
    root_fd = fixture_fd = None
    proc = None
    try:
        integrity = load('raw_probe_tooling_integrity', ROOT / 'boot/verify-tooling.py').verify()
        if not integrity['success']:
            raise ValueError('Pinned QEMU/tooling runtime integrity failed')
        report['tooling_integrity'] = integrity
        assets = json.loads((ROOT / 'boot/boot-assets.lock.json').read_text())
        for name in ('qemu', 'kernel'):
            if prepare.sha(Path(assets[name]['path']).read_bytes()) != assets[name]['sha256']:
                raise ValueError('Pinned executable asset changed: ' + name)
        report['assets'] = {name: assets[name] for name in ('qemu', 'kernel')}
        bootstrap, plan = assemble(out)
        report['fixture_created'] = True
        report['assembly'] = plan
        fixture_fd, report['fixture_before'] = host_fixture.open_fixture(out)
        root_fd = root_image.open_image(ROOT)
        report['root_sha256_before'] = fd_hash(root_fd)
        if report['root_sha256_before'] != prepare.ROOT_SHA:
            raise ValueError('Accepted immutable root hash changed')
        if disk_free() < RESERVE or available() < 3 * 1024**3:
            raise ValueError('Resource reserve changed before VM launch')
        args = command(assets, bootstrap, root_fd, fixture_fd)
        report['command'] = args
        with (result / 'serial.txt').open('xb') as serial, (result / 'qemu-stderr.txt').open('xb') as err:
            start = time.monotonic()
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=serial, stderr=err,
                                    pass_fds=(root_fd, fixture_fd), start_new_session=True,
                                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            report['boot_tested'] = True
            report['peak_qemu_rss_kib'] = 0
            while proc.poll() is None:
                if time.monotonic() - start > 120:
                    raise TimeoutError('Synthetic VM wall deadline exceeded')
                try:
                    status = Path(f'/proc/{proc.pid}/status').read_text()
                    for line in status.splitlines():
                        if line.startswith(('VmHWM:', 'VmRSS:')):
                            report['peak_qemu_rss_kib'] = max(report['peak_qemu_rss_kib'], int(line.split()[1]))
                except FileNotFoundError:
                    pass
                if report['peak_qemu_rss_kib'] * 1024 > report['host_rss_cap_bytes']:
                    raise MemoryError('Synthetic QEMU RSS cap exceeded')
                if available() < report['host_available_reserve_bytes']:
                    raise MemoryError('Host available memory reserve crossed')
                if disk_free() < RESERVE or serial.tell() + err.tell() > 8 * 1024**2:
                    raise ValueError('Synthetic log/disk reserve exceeded')
                time.sleep(.1)
            report['elapsed_seconds'] = round(time.monotonic()-start, 3)
            report['qemu_returncode'] = proc.returncode
        log = (result / 'serial.txt').read_text(errors='replace')
        markers = [line.removeprefix('ROKO_RAW_SYNTHETIC_RESULT ') for line in log.splitlines()
                   if line.startswith('ROKO_RAW_SYNTHETIC_RESULT ')]
        if len(markers) != 1:
            raise ValueError('Expected one guest transport receipt')
        report['guest'] = json.loads(markers[0])
        report['lifecycle_passed'] = proc.returncode == 0 and 'ROKO_RAW_SYNTHETIC_EXIT 0' in log and 'Power down' in log
        if not report['guest'].get('passed') or not report['lifecycle_passed']:
            raise ValueError('Synthetic guest proof or lifecycle failed')
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        terminate(proc)
        report['qemu_running_after_cleanup'] = proc is not None and proc.poll() is None
        if fixture_fd is not None:
            try:
                report['fixture_after'] = host_fixture.verify(fixture_fd, report.get('fixture_before'))
                report['fixture_unchanged'] = report['fixture_after'] == report.get('fixture_before')
            except BaseException as error:
                report['errors'].append('Fixture postcheck: ' + str(error))
            os.close(fixture_fd)
        if root_fd is not None:
            try:
                report['root_sha256_after'] = fd_hash(root_fd)
                report['root_unchanged'] = report['root_sha256_after'] == report.get('root_sha256_before') == prepare.ROOT_SHA
            except BaseException as error:
                report['errors'].append('Root postcheck: ' + str(error))
            os.close(root_fd)
        report['free_disk_after'] = disk_free()
        report['passed'] = (not report['errors'] and report.get('lifecycle_passed') is True
                            and report.get('fixture_unchanged') is True and report.get('root_unchanged') is True)
        for name in ('serial.txt', 'qemu-stderr.txt'):
            path = result / name
            if path.exists():
                report[name + '_sha256'] = prepare.sha(path.read_bytes())
        report['source_sha256'] = {p.name: prepare.sha(p.read_bytes()) for p in HERE.glob('*.py')}
        (result / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        _, plan = prepare.tiny_delta()
        print(json.dumps(plan, indent=2))
    else:
        outcome = run()
        print(json.dumps({k: outcome[k] for k in ['passed', 'boot_tested', 'result_path', 'errors', 'free_disk_after']}, indent=2))
        raise SystemExit(0 if outcome['passed'] else 1)
