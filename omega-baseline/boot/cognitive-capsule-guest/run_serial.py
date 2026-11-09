#!/usr/bin/env python3
"""Bounded serial-only cognitive VM runner. Explicit --run after review/lane grant."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import time

import harness

ROOT = harness.ROOT
RESULTS = ROOT / 'results/cognitive-capsule-guest'
BUILDS = ROOT / 'build/cognitive-capsule-guest'
root_image = harness.load('cognitive_root_image', ROOT / 'boot/disk-root-guest/image.py')


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise ValueError('Host MemAvailable not available')


def artifact_bytes():
    total = 0
    for directory in (ROOT / 'build-src/cognitive-capsule-guest', RESULTS, BUILDS):
        if directory.exists():
            total += sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())
    return total


def fd_hash(fd, seconds=60):
    deadline = time.monotonic() + seconds
    digest = hashlib.sha256()
    offset = 0
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError('Root integrity hash60s deadline exceeded')
        data = os.pread(fd, 4 * 1024**2, offset)
        if not data:
            return digest.hexdigest()
        digest.update(data); offset += len(data)


def metadata(fd):
    s = os.fstat(fd)
    return {'device': s.st_dev, 'inode': s.st_ino, 'size': s.st_size,
            'mode': stat.S_IMODE(s.st_mode), 'mtime_ns': s.st_mtime_ns,
            'ctime_ns': s.st_ctime_ns}


def process_identity(pid):
    fields = Path('/proc/%d/stat' % pid).read_text().rpartition(')')[2].split()
    return {'pid': pid, 'start_ticks': int(fields[19]), 'pgrp': int(fields[2]),
            'ppid': int(fields[1]), 'state': fields[0]}


def group_members(group):
    found = []
    for path in Path('/proc').iterdir():
        if path.name.isdecimal():
            try:
                identity = process_identity(int(path.name))
                if identity['pgrp'] == group:
                    found.append(identity)
            except (FileNotFoundError, ProcessLookupError):
                pass
    return found


def parent_guard(parent):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_PDEATHSIG failed')
    if os.getppid() != parent:
        os._exit(125)


def terminate(proc):
    if proc is None:
        return {'before': [], 'after': [], 'leader_running': False}
    before = group_members(proc.pid)
    for sig, seconds in ((signal.SIGTERM, 3), (signal.SIGKILL, 3)):
        if proc.poll() is None or group_members(proc.pid):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            pass
        if proc.poll() is not None and not group_members(proc.pid):
            break
    after = group_members(proc.pid)
    if proc.poll() is None or after:
        raise TimeoutError('QEMU process/group remains after bounded cleanup')
    return {'before': before, 'after': after, 'leader_running': False,
            'scope': 'Independent same-process-group observation, not detached-descendant containment'}


def command(assets, bootstrap, root_fd):
    return [assets['qemu']['path'], '-no-user-config', '-nodefaults',
            '-machine', 'q35,accel=tcg', '-m', '2048', '-smp', '2', '-cpu', 'max',
            '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none',
            '-no-reboot', '-kernel', assets['kernel']['path'], '-initrd', str(bootstrap),
            '-append', 'console=ttyS0 rdinit=/init panic=1'] + root_image.attach(root_fd)


def interrupted(signum, frame):
    raise InterruptedError('Cognitive runner interrupted by signal ' + str(signum))


def expired(signum, frame):
    raise TimeoutError('Runner480s operating budget exhausted; cleanup reserve remains')


def run():
    plan = harness.validate()
    RESULTS.mkdir(mode=0o700, exist_ok=True); BUILDS.mkdir(mode=0o700, exist_ok=True)
    lane = os.open(ROOT / 'results/granite-model-guest/recovery-lane.lock',
                   os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lane, fcntl.LOCK_EX | fcntl.LOCK_NB)
    attempt = 1
    while (RESULTS / ('attempt-%d' % attempt)).exists() or (BUILDS / ('attempt-%d' % attempt)).exists():
        attempt += 1
    result = RESULTS / ('attempt-%d' % attempt)
    out = BUILDS / ('attempt-%d' % attempt)
    result.mkdir(mode=0o700)
    report = {'passed': False, 'status': 'preflight', 'boot_tested': False,
              'graphical_cognition_tested': False, 'model_attached': False,
              'network_enabled': False, 'host_directory_shared': False,
              'executed_actions': 0, 'authorizes_actions': False, 'plan': plan,
              'runner': process_identity(os.getpid()), 'errors': [],
              'result_path': str(result.relative_to(ROOT)), 'peak_qemu_rss_bytes': 0,
              'minimum_host_available_bytes': available(),
              'parent_death_sigkill_configured': True,
              'actual_parent_death_test_performed': False}
    root_fd = proc = None
    started = time.monotonic(); vm_started = None
    prior = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    prior_alarm = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, plan['runner_operating_seconds'])
    def persist(phase):
        report['status'] = phase
        report['heartbeat_unix_seconds'] = time.time()
        report['total_elapsed_seconds'] = round(time.monotonic() - started, 3)
        if vm_started is not None:
            report['vm_elapsed_seconds'] = round(time.monotonic() - vm_started, 3)
        serial = result / 'serial.txt'
        if serial.exists():
            text = serial.read_text(errors='replace')
            complete = text.splitlines() if text.endswith('\n') else text.splitlines()[:-1]
            phases = [x for x in complete if x.startswith('ROKO_COGNITIVE_PHASE ')]
            report['last_guest_phase'] = phases[-1] if phases else None
        atomic_json(result / 'progress.json', report)
    try:
        persist('preflight')
        if available() < plan['host_prelaunch_available_bytes'] or shutil.disk_usage(ROOT).free < harness.DISK_RESERVE + 64 * 1024**2:
            raise ValueError('Need5GiB host available and4GiB disk reserve plus64MiB before launch')
        if artifact_bytes() > harness.TOTAL_ARTIFACT_CAP - 64 * 1024**2:
            raise ValueError('Cognitive artifact512MiB budget has insufficient archive/log headroom')
        report['tooling_integrity'] = harness.load('cognitive_tooling_integrity', ROOT / 'boot/verify-tooling.py').verify()
        if not report['tooling_integrity']['success']:
            raise ValueError('Pinned workspace tooling integrity failed')
        assets = json.loads((ROOT / 'boot/boot-assets.lock.json').read_text())
        for name in ('qemu', 'kernel'):
            if harness.sha(Path(assets[name]['path']).read_bytes()) != assets[name]['sha256']:
                raise ValueError('Pinned asset changed: ' + name)
        root_fd = root_image.open_image(ROOT)
        report['root_before'] = metadata(root_fd)
        report['root_sha256_before'] = fd_hash(root_fd)
        if report['root_sha256_before'] != harness.ROOT_SHA:
            raise ValueError('Accepted immutable root hash changed')
        persist('assembling-reviewed-overlay')
        bootstrap, report['assembly'] = harness.assemble(out)
        args = command(assets, bootstrap, root_fd); report['command'] = args
        if available() < plan['host_prelaunch_available_bytes'] or shutil.disk_usage(ROOT).free < harness.DISK_RESERVE:
            raise ValueError('Resource floors changed during preparation')
        persist('ready-to-launch')
        parent = os.getpid()
        with (result / 'serial.txt').open('xb') as serial, (result / 'qemu-stderr.txt').open('xb') as err:
            vm_started = time.monotonic()
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=serial, stderr=err,
                                    pass_fds=(root_fd,), start_new_session=True,
                                    preexec_fn=lambda: parent_guard(parent),
                                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            report.update(boot_tested=True, qemu=process_identity(proc.pid))
            persist('running')
            print(json.dumps({'started': True, 'result_path': report['result_path']}), flush=True)
            next_update = time.monotonic() + 5
            while proc.poll() is None:
                if time.monotonic() - vm_started >= plan['vm_seconds']:
                    raise TimeoutError('Serial cognitive VM300s deadline exceeded')
                try:
                    for line in Path('/proc/%d/status' % proc.pid).read_text().splitlines():
                        if line.startswith(('VmRSS:', 'VmHWM:')):
                            report['peak_qemu_rss_bytes'] = max(report['peak_qemu_rss_bytes'], int(line.split()[1]) * 1024)
                except FileNotFoundError:
                    pass
                current = available()
                report['minimum_host_available_bytes'] = min(report['minimum_host_available_bytes'], current)
                if current < plan['host_available_floor_bytes']:
                    raise MemoryError('Host2GiB available-memory floor crossed')
                if report['peak_qemu_rss_bytes'] > plan['qemu_rss_cap_bytes']:
                    raise MemoryError('QEMU3GiB RSS cap crossed')
                if shutil.disk_usage(ROOT).free < harness.DISK_RESERVE:
                    raise ValueError('Host4GiB disk floor crossed')
                if serial.tell() + err.tell() > 2 * 1024**2:
                    raise ValueError('Serial/stderr2MiB log cap crossed')
                if time.monotonic() >= next_update:
                    if artifact_bytes() > harness.TOTAL_ARTIFACT_CAP:
                        raise ValueError('Cognitive512MiB artifact cap crossed')
                    persist('running'); next_update = time.monotonic() + 5
                time.sleep(.1)
        report['qemu_returncode'] = proc.returncode
        log = (result / 'serial.txt').read_text(errors='replace')
        marker = 'ROKO_COGNITIVE_GUEST_RESULT '
        records = [line[len(marker):] for line in log.splitlines() if line.startswith(marker)]
        if len(records) != 1 or len(records[0].encode()) > 131072:
            raise ValueError('Missing/ambiguous/oversized serial cognitive receipt')
        report['guest'] = json.loads(records[0])
        report['lifecycle_passed'] = (proc.returncode == 0 and 'ROKO_COGNITIVE_GUEST_EXIT 0' in log.splitlines()
                                      and 'Power down' in log and 'ROKO_COGNITIVE_GUEST_WATCHDOG' not in log)
        if not report['guest'].get('passed') or not report['lifecycle_passed']:
            raise ValueError('Guest cognitive/clean-poweroff gate failed')
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        # Reserve bounded cleanup after the operating timer. Do not interrupt it
        # with repeated signals; root posthash itself has a60s monotonic deadline.
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig in prior:
            signal.signal(sig, signal.SIG_IGN)
        try:
            report['host_process_cleanup'] = terminate(proc)
        except BaseException as error:
            report['errors'].append('QEMU cleanup: ' + str(error))
        if root_fd is not None:
            try:
                report['root_sha256_after'] = fd_hash(root_fd)
                report['root_after'] = metadata(root_fd)
                report['root_unchanged'] = (report['root_after'] == report.get('root_before') and
                                           report['root_sha256_after'] == report.get('root_sha256_before') == harness.ROOT_SHA)
                if not report['root_unchanged']:
                    raise ValueError('Readonly root postcheck differs')
            except BaseException as error:
                report['errors'].append('Root postcheck: ' + str(error))
            finally:
                os.close(root_fd)
        report['qemu_running_after_cleanup'] = proc is not None and proc.poll() is None
        report['free_disk_after'] = shutil.disk_usage(ROOT).free
        report['artifact_bytes_after'] = artifact_bytes()
        report['passed'] = not report['errors'] and report.get('lifecycle_passed') is True and report.get('root_unchanged') is True and not report['qemu_running_after_cleanup']
        persist('complete' if report['passed'] else 'failed')
        atomic_json(result / 'validation.json', report)
        os.close(lane)
        for sig, handler in prior.items():
            signal.signal(sig, handler)
        signal.signal(signal.SIGALRM, prior_alarm)
    print(json.dumps({key: report[key] for key in ('passed', 'result_path', 'errors', 'boot_tested', 'graphical_cognition_tested')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print(json.dumps(harness.validate(), indent=2))
    else:
        raise SystemExit(0 if run()['passed'] else 1)
