#!/usr/bin/env python3
"""Linux bounded inference supervision, including caller death and descendants.

Own session required. This supervises a trusted native runtime, not hostile code.
No files, commands or limits are derived from model output.
"""
import argparse
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def process(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'parent': int(fields[1]),
                'group': int(fields[2]), 'start': int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def descendants(parent, known):
    rows = {}
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            row = process(int(entry.name))
            if row:
                rows[row['pid']] = row
    # Match identity, not a potentially reused process ID.
    live = {pid for pid, stamp in known.items() if pid in rows and rows[pid]['start'] == stamp}
    live.add(parent)
    changed = True
    while changed:
        changed = False
        for pid, row in rows.items():
            if row['parent'] in live and pid not in live:
                live.add(pid)
                known[pid] = row['start']
                changed = True
    return {pid: rows[pid] for pid in live if pid != parent and pid in rows}


def stop_children(known):
    # Never signal a group that might contain the caller or other processes.
    # The subreaper adopts orphaned descendants even if they made a new session.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        rows = descendants(os.getpid(), known)
        alive = {pid: row for pid, row in rows.items() if row['state'] != 'Z'}
        for pid, row in alive.items():
            current = process(pid)
            if current and current['start'] == row['start']:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        while True:
            try:
                child, _ = os.waitpid(-1, os.WNOHANG)
                if child == 0:
                    break
            except ChildProcessError:
                break
        if not alive:
            return
        time.sleep(.02)
    if any(row['state'] != 'Z' for row in descendants(os.getpid(), known).values()):
        raise RuntimeError('Descendant cleanup did not complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--parent-start', type=int, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if (os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()
            or not 0 < args.seconds <= 300 or args.parent_pid <= 1
            or not command or not Path(command[0]).is_absolute()):
        raise ValueError('Expected own session, bounded deadline and explicit absolute command')
    interrupted = []
    def mark(signum, _frame):
        interrupted.append(signum)
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, mark)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    # PR_SET_CHILD_SUBREAPER=36, PR_SET_PDEATHSIG=1.
    if libc.prctl(36, 1, 0, 0, 0) or libc.prctl(1, signal.SIGTERM, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'Required Linux supervision unavailable')
    def parent_alive():
        parent = process(args.parent_pid)
        return bool(parent and parent['start'] == args.parent_start and parent['state'] != 'Z')
    if not parent_alive() or os.getppid() != args.parent_pid or interrupted:
        return 125
    known = {}
    native = None
    reason = 'native-exit'
    code = 125
    started = time.monotonic()
    try:
        native = subprocess.Popen(command, close_fds=True, start_new_session=False)
        row = process(native.pid)
        if row:
            known[native.pid] = row['start']
        while True:
            descendants(os.getpid(), known)
            if interrupted or not parent_alive():
                reason = 'caller-cancelled-or-exited'
                code = 125
                break
            if time.monotonic() - started >= args.seconds:
                reason = 'native-deadline'
                code = 124
                break
            result = native.poll()
            if result is not None:
                code = result if result >= 0 else 128 - result
                break
            time.sleep(.02)
    finally:
        stop_children(known)
        if native is not None:
            try:
                native.wait(timeout=1)
            except ChildProcessError:
                pass
        print(f'ROKO_SUPERVISOR reason={reason} descendants_cleaned=1', file=sys.stderr, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
