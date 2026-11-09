"""Bind a synchronous native child to its live calling process on Linux."""
import ctypes
import os
import signal


def bind_parent(expected):
    if type(expected) is not int or expected<=1 or os.getppid()!=expected:
        raise RuntimeError('Native caller identity changed before binding')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(),'Cannot bind native caller lifetime')
    if os.getppid()!=expected:
        raise RuntimeError('Native caller died during binding')
