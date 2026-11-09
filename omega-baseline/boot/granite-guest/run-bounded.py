#!/usr/bin/env python3
"""Run one approved build/profile command with a wall and memory stop policy."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time


def available():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:')))


def processes():
    rows = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = entry.joinpath('stat').read_text().rsplit(')', 1)[1].split()
            rows[int(entry.name)] = {'parent': int(fields[1]), 'group': int(fields[2]),
                                    'rss_kib': int(fields[21]) * os.sysconf('SC_PAGE_SIZE') // 1024}
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--start-available-kib', type=int, required=True)
    parser.add_argument('--reserve-kib', type=int, required=True)
    parser.add_argument('--max-rss-kib', type=int, required=True)
    parser.add_argument('--minimum-free-bytes', type=int, default=0)
    parser.add_argument('--disk-path', type=Path, default=Path.cwd())
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.out.exists() or not 1 <= args.seconds <= 1800:
        raise ValueError('Invalid command, deadline, or existing result destination')
    initial = available()
    if initial < args.start_available_kib:
        raise RuntimeError('Insufficient available memory for admission')
    disk_free = shutil.disk_usage(args.disk_path).free
    if disk_free < args.minimum_free_bytes:
        raise RuntimeError('Insufficient free disk for admission')
    args.out.mkdir(parents=True, mode=0o700)
    start = time.monotonic()
    report = {'command': command, 'initial_available_kib': initial,
              'reserve_kib': args.reserve_kib, 'max_group_rss_kib_policy': args.max_rss_kib,
              'deadline_seconds': args.seconds, 'peak_sampled_descendant_rss_kib': 0,
              'minimum_available_kib': initial, 'termination_reason': None}
    report.update(minimum_free_disk_bytes=disk_free, disk_reserve_bytes=args.minimum_free_bytes)
    log_path = args.out / 'output.txt'
    groups = set()
    known = set()
    with log_path.open('wb') as log:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True)
        groups.add(proc.pid)
        known.add(proc.pid)
        while proc.poll() is None:
            rows = processes()
            pending = True
            while pending:
                pending = False
                for pid, row in rows.items():
                    if row['parent'] in known and pid not in known:
                        known.add(pid)
                        pending = True
            descendants = [row for pid, row in rows.items() if pid in known]
            groups.update(row['group'] for row in descendants)
            rss = sum(row['rss_kib'] for row in descendants)
            free = available()
            disk_free = shutil.disk_usage(args.disk_path).free
            report['minimum_free_disk_bytes'] = min(report['minimum_free_disk_bytes'], disk_free)
            report['peak_sampled_descendant_rss_kib'] = max(report['peak_sampled_descendant_rss_kib'], rss)
            report['minimum_available_kib'] = min(report['minimum_available_kib'], free)
            reason = None
            if time.monotonic() - start >= args.seconds:
                reason = 'wall deadline'
            elif free < args.reserve_kib:
                reason = 'host available memory reserve'
            elif rss > args.max_rss_kib:
                reason = 'descendant RSS policy'
            elif disk_free < args.minimum_free_bytes:
                reason = 'free disk reserve'
            elif log_path.stat().st_size > 4 * 1024 * 1024:
                reason = 'log size limit'
            if reason:
                report['termination_reason'] = reason
                break
            time.sleep(.1)
        if report['termination_reason']:
            for group in groups:
                try:
                    os.killpg(group, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            # Kill every admitted descendant group even if its original leader exited.
            for group in groups:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        proc.wait(timeout=5)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    report.update(returncode=proc.returncode, elapsed_seconds=round(time.monotonic() - start, 3),
                  child_max_rss_kib=usage.ru_maxrss, minor_faults=usage.ru_minflt,
                  major_faults=usage.ru_majflt, user_seconds=usage.ru_utime,
                  system_seconds=usage.ru_stime, final_available_kib=available(),
                  observed_process_groups=sorted(groups))
    (args.out / 'monitor.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if proc.returncode == 0 and report['termination_reason'] is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
