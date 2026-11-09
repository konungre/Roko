#!/usr/bin/env python3
"""Same admitted extended guest, durable receipts and crash-safe QEMU lifecycle."""
import argparse
import ctypes
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'boot/granite-model-guest-extended'))
_spec = importlib.util.spec_from_file_location('extended_runner', ROOT / 'boot/granite-model-guest-extended/run_model.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def child_guard(parent):
    # Called after fork and before exec. Recheck after prctl to close death race.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_PDEATHSIG failed')
    if os.getppid() != parent:
        os._exit(125)


def process_identity(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
    return {'pid': pid, 'start_ticks': int(fields[19]),
            'pid_namespace': os.readlink(f'/proc/{pid}/ns/pid'),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def cancelled(signum, frame):
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal.SIG_IGN)
    raise InterruptedError('Runner received signal ' + str(signum))


def run():
    result_parent = ROOT / 'results/granite-model-guest'
    build_parent = ROOT / 'build/granite-model-guest'
    result_parent.mkdir(mode=0o700, exist_ok=True)
    build_parent.mkdir(mode=0o700, exist_ok=True)
    lane = os.open(result_parent / 'recovery-lane.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lane, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root_fd = model_fd = proc = result = None
    report = {'passed': False, 'status': 'preflight', 'boot_tested': False, 'model_attached': False,
              'model_loaded': False, 'host_directory_shared': False, 'network_enabled': False,
              'memory_mib': 6144, 'tcg_cpus': 1, 'vm_wall_seconds': 1200,
              'host_rss_cap_bytes': 7 * 1024**3, 'host_available_reserve_bytes': 2 * 1024**3,
              'errors': [], 'runtime_payload_assembled': False, 'runner': process_identity(os.getpid()),
              'heartbeat_interval_seconds': 5, 'child_parent_death_signal': 'SIGKILL',
              'prior_attempt_2': 'indeterminate interrupted attempt; preserved unchanged'}
    prior_handlers = {sig: signal.signal(sig, cancelled) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    start = None

    def persist(phase):
        report['status'] = phase
        report['heartbeat_unix_seconds'] = time.time()
        if start is not None:
            report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        if result is not None:
            for name in ('serial.txt', 'qemu-stderr.txt'):
                p = result / name
                if p.exists():
                    report[name + '_bytes'] = p.stat().st_size
            serial_path = result / 'serial.txt'
            if serial_path.exists():
                lines = serial_path.read_text(errors='replace').splitlines()
                phases = [line for line in lines if line.startswith(('ROKO_GRANITE_GUEST_PHASE ', 'ROKO_GRANITE_GUEST_OBSERVATION ', 'ROKO_GRANITE_GUEST_EXIT '))]
                report['last_guest_phase'] = phases[-1] if phases else None
            atomic_json(result / 'progress.json', report)

    try:
        report['free_disk_before'] = base.disk_free()
        if report['free_disk_before'] < base.RESERVE + 64 * 1024**2 or base.available() < 8 * 1024**3:
            raise ValueError('Requires 4 GiB disk plus 64 MiB and 8 GiB MemAvailable')
        integrity = base.load('recovery_tooling_integrity', ROOT / 'boot/verify-tooling.py').verify()
        if not integrity['success']:
            raise ValueError('Pinned tooling integrity failed')
        report['tooling_integrity'] = integrity
        assets = json.loads((ROOT / 'boot/boot-assets.lock.json').read_text())
        for name in ('qemu', 'kernel'):
            if base.prepare.sha(Path(assets[name]['path']).read_bytes()) != assets[name]['sha256']:
                raise ValueError('Pinned executable changed: ' + name)
        report['assets'] = {name: assets[name] for name in ('qemu', 'kernel')}
        _, plan = base.prepared_delta(execution_admitted=True)
        # Exclusive root lock is inherited by QEMU, protecting across PID namespaces.
        root_fd = base.root_image.open_image(ROOT)
        report['root_before'] = base.host_model.metadata(os.fstat(root_fd))
        began = time.monotonic()
        report['root_sha256_before'] = base.fd_hash(root_fd)
        report['host_root_hash_before_seconds'] = round(time.monotonic() - began, 3)
        if report['root_sha256_before'] != plan['root_sha256']:
            raise ValueError('Accepted root changed')
        began = time.monotonic()
        model_fd, report['model_before'] = base.host_model.open_model()
        # No concurrent reader from the interrupted test may still own its flock.
        fcntl.flock(model_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report['host_model_hash_before_seconds'] = round(time.monotonic() - began, 3)
        if base.disk_free() < base.RESERVE + 64 * 1024**2 or base.available() < 8 * 1024**3:
            raise ValueError('Reserve changed during preflight')
        attempt = 1
        while (build_parent / f'attempt-{attempt}').exists() or (result_parent / f'attempt-{attempt}').exists():
            attempt += 1
        out, result = build_parent / f'attempt-{attempt}', result_parent / f'attempt-{attempt}'
        out.mkdir(mode=0o700)
        result.mkdir(mode=0o700)
        report['result_path'] = str(result.relative_to(ROOT))
        report['source_sha256'] = {str(p.relative_to(ROOT)): base.prepare.sha(p.read_bytes()) for p in list(HERE.glob('*.py')) + list(base.HERE.glob('*.py'))}
        persist('integrity-admitted')
        bootstrap, report['assembly'] = base.assemble(out)
        report['runtime_payload_assembled'] = True
        prior = json.loads((build_parent / 'attempt-2/assembly.json').read_text())
        if report['assembly']['initramfs_sha256'] != prior['initramfs_sha256']:
            raise ValueError('Guest payload must remain byte-identical to attempt 2')
        report['guest_identical_to_attempt_2'] = True
        args = base.command(assets, bootstrap, root_fd, model_fd, report['model_before'])
        report['command'] = args
        if base.disk_free() < base.RESERVE or base.available() < 8 * 1024**3:
            raise ValueError('Reserve changed before launch')
        persist('ready-to-launch')
        with (result / 'serial.txt').open('xb') as serial, (result / 'qemu-stderr.txt').open('xb') as err:
            start = time.monotonic()
            parent = os.getpid()
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=serial, stderr=err,
                                    pass_fds=(root_fd, model_fd), start_new_session=True,
                                    preexec_fn=lambda: child_guard(parent),
                                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            report.update(boot_tested=True, model_attached=True, qemu=process_identity(proc.pid), peak_qemu_rss_kib=0)
            persist('running')
            print(json.dumps({'started': True, 'result_path': report['result_path'], 'qemu': report['qemu']}), flush=True)
            next_heartbeat = time.monotonic() + 5
            while proc.poll() is None:
                if time.monotonic() - start > 1200:
                    raise TimeoutError('Real-model VM wall deadline exceeded')
                try:
                    for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines():
                        if line.startswith(('VmHWM:', 'VmRSS:')):
                            report['peak_qemu_rss_kib'] = max(report['peak_qemu_rss_kib'], int(line.split()[1]))
                except FileNotFoundError:
                    pass
                report['host_available_bytes'] = base.available()
                report['free_disk_bytes'] = base.disk_free()
                if report['peak_qemu_rss_kib'] * 1024 > report['host_rss_cap_bytes']:
                    raise MemoryError('Real-model QEMU RSS cap exceeded')
                if report['host_available_bytes'] < report['host_available_reserve_bytes']:
                    raise MemoryError('Host available memory reserve crossed')
                if report['free_disk_bytes'] < base.RESERVE or serial.tell() + err.tell() > 8 * 1024**2:
                    raise ValueError('Real-model log/disk reserve exceeded')
                if time.monotonic() >= next_heartbeat:
                    persist('running')
                    next_heartbeat = time.monotonic() + 5
                time.sleep(.1)
            report['qemu_returncode'] = proc.returncode
        persist('guest-exited')
        log = (result / 'serial.txt').read_text(errors='replace')
        markers = [line.removeprefix('ROKO_GRANITE_GUEST_RESULT ') for line in log.splitlines() if line.startswith('ROKO_GRANITE_GUEST_RESULT ')]
        if len(markers) != 1:
            raise ValueError('Expected one guest transport receipt')
        report['guest'] = json.loads(markers[0])
        report['model_loaded'] = report['guest'].get('model_loaded')
        report['format_valid'] = report['guest'].get('format_valid', False)
        report['accuracy_passed'] = report['guest'].get('accuracy_passed', False)
        report['lifecycle_passed'] = proc.returncode == 0 and any('ROKO_GRANITE_GUEST_EXIT ' + str(code) in log for code in (0, 1)) and 'Power down' in log
        if not report['guest'].get('passed') or not report['lifecycle_passed']:
            raise ValueError('Real-model inference/accuracy or lifecycle gate failed')
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        try:
            persist('cleanup')
        finally:
            base.terminate(proc)
        if proc is not None:
            report['qemu_returncode'] = proc.returncode
        report['qemu_running_after_cleanup'] = proc is not None and proc.poll() is None
        if model_fd is not None:
            try:
                began = time.monotonic()
                report['model_after'] = base.host_model.verify(model_fd, report.get('model_before'))
                report['host_model_hash_after_seconds'] = round(time.monotonic() - began, 3)
                report['model_unchanged'] = report['model_after'] == report.get('model_before')
            except BaseException as error:
                report['errors'].append('Model postcheck: ' + str(error))
            os.close(model_fd)
        if root_fd is not None:
            try:
                began = time.monotonic()
                report['root_sha256_after'] = base.fd_hash(root_fd)
                report['host_root_hash_after_seconds'] = round(time.monotonic() - began, 3)
                report['root_after'] = base.host_model.metadata(os.fstat(root_fd))
                report['root_unchanged'] = report['root_after'] == report.get('root_before') and report['root_sha256_after'] == report.get('root_sha256_before') == plan['root_sha256']
            except BaseException as error:
                report['errors'].append('Root postcheck: ' + str(error))
            os.close(root_fd)
        report['free_disk_after'] = base.disk_free()
        report['passed'] = not report['errors'] and report.get('lifecycle_passed') is True and report.get('model_unchanged') is True and report.get('root_unchanged') is True
        if result is not None:
            for name in ('serial.txt', 'qemu-stderr.txt'):
                p = result / name
                if p.exists():
                    report[name + '_sha256'] = base.prepare.sha(p.read_bytes())
            persist('completed')
            atomic_json(result / 'validation.json', report)
        else:
            print(json.dumps({'admission_failed': True, 'errors': report['errors']}), flush=True)
        os.close(lane)
        for sig, handler in prior_handlers.items():
            signal.signal(sig, handler)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.run:
        outcome = run()
        print(json.dumps({k: outcome.get(k) for k in ('passed', 'boot_tested', 'result_path', 'errors', 'free_disk_after')}), flush=True)
        raise SystemExit(0 if outcome['passed'] else 1)
    print(json.dumps(base.prepared_delta()[1], indent=2))
