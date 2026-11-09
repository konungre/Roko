"""Fixed trusted launch, no arbitrary commands or environment from the request."""
import ctypes
import errno
import os
import resource
import signal
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from paths import HERE, SWI, PYTHON, PETTA, UPSTREAM, SYSTEM

def main():
    if len(sys.argv) != 2 or sys.argv[1] != 'nars':
        raise ValueError('Only fixed NAL-1 worker')
    parent = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if parent == 1 or libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != parent:
        raise RuntimeError('Parent-death binding unavailable')
    for key, limits in ((resource.RLIMIT_CORE,(0,0)), (resource.RLIMIT_CPU,(20,21)),
            (resource.RLIMIT_AS,(512*1024**2,512*1024**2)),
            (resource.RLIMIT_FSIZE,(16384,16384)), (resource.RLIMIT_NOFILE,(64,64))):
        resource.setrlimit(key, limits)
    # This is child-only filtering, inherited across exec. It does not change
    # host networking and does not claim filesystem confinement.
    lib = ctypes.CDLL(str(SYSTEM/'libseccomp.so.2'), use_errno=True)
    lib.seccomp_init.argtypes=[ctypes.c_uint32]; lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]; lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
    lib.seccomp_load.argtypes=[ctypes.c_void_p]; lib.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=lib.seccomp_init(0x7fff0000)
    if not ctx: raise RuntimeError('seccomp initialization failed')
    try:
        for name in ('socket','socketpair','connect','bind','listen','accept','accept4','sendto','sendmsg','sendmmsg','recvfrom','recvmsg','recvmmsg'):
            number=lib.seccomp_syscall_resolve_name(name.encode())
            if number < 0 or lib.seccomp_rule_add(ctx,0x00050000|errno.EPERM,number,0):
                raise RuntimeError('seccomp network rule failed')
        if lib.seccomp_load(ctx): raise RuntimeError('seccomp installation failed')
    finally: lib.seccomp_release(ctx)
    library=':'.join(map(str,(SYSTEM,PYTHON/'lib',SWI/'lib/x86_64-linux')))
    loader=str(SYSTEM/'ld-linux-x86-64.so.2')
    args=[loader,'--inhibit-cache','--library-path',library,str(SWI/'bin/x86_64-linux/swipl'),
          '--stack-limit=64m','-q','-f','none','--no-packs','-s',str(HERE/('worker-'+sys.argv[1]+'.pl')),'--','silent']
    env={'PATH':'/nonexistent','HOME':os.getcwd(),'TMPDIR':os.getcwd(),
         'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','SWI_HOME_DIR':str(SWI),
         'PETTA_PATH':str(PETTA),'ROKO_NARS_SOURCE':str(UPSTREAM),
         'PYTHONHOME':str(PYTHON),'PYTHONPATH':str(HERE),
         'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1',
         'LD_LIBRARY_PATH':library,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
    os.execve(loader,args,env)
if __name__=='__main__':main()
