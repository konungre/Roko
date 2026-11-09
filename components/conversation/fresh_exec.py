#!/usr/bin/env python3
"""Bind the fixed worker to its launcher's lifetime before installing seccomp.

The launcher creates this process on its long-lived main thread. The parent
identity check closes the race where it exits before PR_SET_PDEATHSIG is set.
The signal survives exec into the no-network wrapper and SWI worker. Native
inference has its own subreaper which observes the worker's exit.
"""
import ctypes
import os
from pathlib import Path
import signal
import sys


def process_identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (OSError, ValueError, IndexError):
        return None


def main():
    parent = int(sys.argv[1])
    stamp = sys.argv[2]
    command = sys.argv[3:]
    if parent <= 1 or not command or not Path(command[0]).is_absolute():
        raise ValueError('Expected parent identity and fixed absolute command')
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                          ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'Required parent-death binding unavailable')
    if os.getppid() != parent or process_identity(parent) != stamp:
        return 125
    os.execv(command[0], command)


if __name__ == '__main__':
    raise SystemExit(main())
