#!/usr/bin/env python3
"""Two fixed direct Omega cases with finite aggregate budget and crash-safe lifecycle."""
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
import prepare_gate
base.prepare = prepare_gate
base.HERE = HERE
_original_delta = base.prepared_delta
_original_command = base.command


def fourcore_delta(execution_admitted=False):
    prepare_gate.validate()
    entries, plan = _original_delta(execution_admitted=execution_admitted)
    plan['bounds']['tcg_cpus'] = 4
    plan['bounds']['native_threads'] = 4
    plan['bounds']['vm_seconds'] = 2100
    plan['bounds']['total_runner_seconds'] = 2400
    plan['case_plan'] = prepare_gate.case_plan()
    plan['request'] = 'Two frozen direct Omega cases: literal_copy and invoice_extraction'
    plan['expected'] = {case['id']:case['args'] for case in plan['case_plan']['cases']}
    plan['native_runtime_unchanged_from_attempt_4'] = True
    plan['host_cpu_quota'] = 'unknown; cgroup filesystem not exposed'
    return entries, plan


def fourcore_command(assets, bootstrap, root_fd, model_fd, admitted):
    args = _original_command(assets, bootstrap, root_fd, model_fd, admitted)
    args[args.index('-machine') + 1] = 'q35'
    args[args.index('-smp') + 1] = '4'
    args += ['-accel', 'tcg,thread=multi']
    return args


base.prepared_delta = fourcore_delta
base.command = fourcore_command


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


def total_timeout(signum, frame):
    raise TimeoutError('Total runner operating budget exhausted; cleanup reserve remains')


def budget_seconds(deadline, maximum=120):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Total runner budget leaves no time for integrity operation')
    return min(maximum, remaining)


def run():
    total_started = time.monotonic()
    operating_deadline = total_started + 2390  # Leave up to ten seconds for stop/receipt.
    result_parent = ROOT / 'results/granite-model-guest'
    build_parent = ROOT / 'build/granite-model-guest'
    result_parent.mkdir(mode=0o700, exist_ok=True)
    build_parent.mkdir(mode=0o700, exist_ok=True)
    lane = os.open(result_parent / 'recovery-lane.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lane, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root_fd = model_fd = proc = result = None
    report = {'passed': False, 'status': 'preflight', 'boot_tested': False, 'model_attached': False,
              'model_loaded': False, 'host_directory_shared': False, 'network_enabled': False,
              'memory_mib': 6144, 'tcg_cpus': 4, 'native_threads': 4, 'tcg_thread_mode': 'multi', 'vm_wall_seconds': 2100,
              'host_rss_cap_bytes': 7 * 1024**3, 'host_available_reserve_bytes': 2 * 1024**3,
              'errors': [], 'runtime_payload_assembled': False, 'runner': process_identity(os.getpid()),
              'heartbeat_interval_seconds': 5, 'child_parent_death_signal': 'SIGKILL',
              'total_runner_seconds': 2400, 'operating_seconds': 2390, 'cleanup_reserve_seconds': 10,
              'prior_attempt_2': 'indeterminate interrupted attempt; preserved unchanged'}
    prior_handlers = {sig: signal.signal(sig, cancelled) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    prior_alarm_handler = signal.signal(signal.SIGALRM, total_timeout)
    signal.setitimer(signal.ITIMER_REAL, budget_seconds(operating_deadline, 2390))
    start = None

    def persist(phase):
        report['status'] = phase
        report['heartbeat_unix_seconds'] = time.time()
        report['total_elapsed_seconds'] = round(time.monotonic() - total_started, 3)
        if start is not None:
            report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        if result is not None:
            for name in ('serial.txt', 'qemu-stderr.txt'):
                p = result / name
                if p.exists():
                    report[name + '_bytes'] = p.stat().st_size
            serial_path = result / 'serial.txt'
            if serial_path.exists():
                content = serial_path.read_text(errors='replace')
                lines = content.splitlines()
                if lines and not content.endswith('\n'):
                    lines.pop()  # An in-flight serial write is not a complete receipt.
                phases = [line for line in lines if line.startswith(('ROKO_GRANITE_GUEST_PHASE ', 'ROKO_GRANITE_GUEST_OBSERVATION ', 'ROKO_GRANITE_GUEST_EXIT '))]
                report['last_guest_phase'] = phases[-1] if phases else None
                report['case_summaries'] = []
                for line in lines:
                    if not line.startswith('ROKO_GRANITE_CASE_RESULT '):
                        continue
                    row = json.loads(line.removeprefix('ROKO_GRANITE_CASE_RESULT '))
                    if row.get('id') not in prepare_gate.CASE_IDS:
                        raise ValueError('Unexpected serial case receipt')
                    report['case_summaries'].append({key: row.get(key) for key in ('id','passed','format_valid','exact_correct','controller_accepted','native_completed','request_seconds','error')})
                    target = result / ('case-' + row['id'] + '.json')
                    if not target.exists():
                        atomic_json(target, row)
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
        report['root_sha256_before'] = base.fd_hash(root_fd, seconds=budget_seconds(operating_deadline))
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
        prepare_gate.validate()
        report['guest_change_from_attempt_4'] = 'Two frozen request/checker fixtures and added evaluation source only; native runtime unchanged'
        report['host_cpu_quota'] = 'unknown; cgroup filesystem not exposed'
        report['host_affinity_cpu_count'] = len(os.sched_getaffinity(0))
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
                if time.monotonic() - start > 2100:
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
        report['measurement_completed'] = report['guest'].get('measurement_completed', False)
        report['failed_accuracy_cases'] = report['guest'].get('failed_accuracy_cases', [])
        if not report['lifecycle_passed']:
            raise ValueError('Guest lifecycle failed')
        if report['guest'].get('runtime_blocker') or not report['measurement_completed']:
            raise ValueError('Representative runtime stopped: ' + str(report['guest'].get('runtime_blocker')))
        if not report['guest'].get('passed'):
            report['errors'].append('AccuracyError: Exact answer/controller gate failed for: ' + ', '.join(report['failed_accuracy_cases']))
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
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
                report['model_after'] = base.host_model.verify(model_fd, report.get('model_before'), seconds=budget_seconds(operating_deadline))
                report['host_model_hash_after_seconds'] = round(time.monotonic() - began, 3)
                report['model_unchanged'] = report['model_after'] == report.get('model_before')
            except BaseException as error:
                report['errors'].append('Model postcheck: ' + str(error))
            os.close(model_fd)
        if root_fd is not None:
            try:
                began = time.monotonic()
                report['root_sha256_after'] = base.fd_hash(root_fd, seconds=budget_seconds(operating_deadline))
                report['host_root_hash_after_seconds'] = round(time.monotonic() - began, 3)
                report['root_after'] = base.host_model.metadata(os.fstat(root_fd))
                report['root_unchanged'] = report['root_after'] == report.get('root_before') and report['root_sha256_after'] == report.get('root_sha256_before') == plan['root_sha256']
            except BaseException as error:
                report['errors'].append('Root postcheck: ' + str(error))
            os.close(root_fd)
        report['free_disk_after'] = base.disk_free()
        report['passed'] = not report['errors'] and report.get('lifecycle_passed') is True and report.get('model_unchanged') is True and report.get('root_unchanged') is True
        report['execution_completed_cleanly'] = report.get('measurement_completed') is True and report.get('lifecycle_passed') is True and report.get('model_unchanged') is True and report.get('root_unchanged') is True
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
        signal.signal(signal.SIGALRM, prior_alarm_handler)
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
