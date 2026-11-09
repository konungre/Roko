#!/usr/bin/env python3
"""Deny new non-Unix sockets while allowing local IPC needed by ChromaDB.
Not a general hostile-code sandbox. Callers must close inherited descriptors.
"""
import ctypes
import ctypes.util
import errno
import os
import sys
class ArgCmp(ctypes.Structure):
    _fields_=[('arg',ctypes.c_uint),('op',ctypes.c_uint),('datum_a',ctypes.c_uint64),('datum_b',ctypes.c_uint64)]
lib=ctypes.CDLL(ctypes.util.find_library('seccomp') or 'libseccomp.so.2')
lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
lib.seccomp_rule_add_array.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint,ctypes.POINTER(ArgCmp)]
lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_release.argtypes=[ctypes.c_void_p]
ctx=lib.seccomp_init(0x7fff0000)
if not ctx:raise SystemExit('Cannot initialize filter')
try:
    # SCMP_CMP_NE = 1; AF_UNIX = 1. Disallow every other domain.
    cmp=ArgCmp(0,1,1,0)
    for name in ('socket','socketpair'):
        n=lib.seccomp_syscall_resolve_name(name.encode())
        if n<0 or lib.seccomp_rule_add_array(ctx,0x00050000|errno.EPERM,n,1,ctypes.byref(cmp)):
            raise SystemExit('Cannot add filter for '+name)
    if lib.seccomp_load(ctx):raise SystemExit('Cannot apply filter')
finally:lib.seccomp_release(ctx)
if len(sys.argv)<2:raise SystemExit('Usage: no-internet.py command [args...]')
os.execvp(sys.argv[1],sys.argv[1:])
