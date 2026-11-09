#!/usr/bin/env python3
"""Linux child-only seccomp network denial; no host settings or ptrace."""
import ctypes
import ctypes.util
import errno
import os
import sys
lib=ctypes.CDLL(ctypes.util.find_library('seccomp') or 'libseccomp.so.2',use_errno=True)
lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_release.argtypes=[ctypes.c_void_p]
ctx=lib.seccomp_init(0x7fff0000)
if not ctx: raise SystemExit('Cannot create seccomp filter')
try:
    for name in ('socket','socketpair','connect','bind','listen','accept','accept4','sendto','sendmsg','sendmmsg','recvfrom','recvmsg','recvmmsg'):
        num=lib.seccomp_syscall_resolve_name(name.encode())
        if num>=0 and lib.seccomp_rule_add(ctx,0x00050000|errno.EPERM,num,0):
            raise SystemExit('Cannot add network denial for '+name)
    if lib.seccomp_load(ctx): raise SystemExit('Cannot load network-denial filter')
finally:
    lib.seccomp_release(ctx)
if len(sys.argv)<2: raise SystemExit('Usage: no-network.py command [args...]')
os.execvp(sys.argv[1],sys.argv[1:])
