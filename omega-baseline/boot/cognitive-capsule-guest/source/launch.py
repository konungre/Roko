"""Child-only 3.13 launcher, execs pinned loader/SWI with embedded 3.12 Janus.

No command or environment is taken from the JSON request. Native execution needs
an independently checked admission in the parent controller, not a CLI toggle.
"""
import ctypes
import os
from pathlib import Path
import resource
import signal


def main():
    parent = os.getppid()
    # No inherited write handles other than the three bounded standard pipes.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent or parent == 1:
        raise RuntimeError('Unable to bind native worker lifetime to controller')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 26))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16384, 16384))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    capsule = Path(__file__).resolve().parents[1]
    library = ':'.join(str(capsule / name) for name in
                       ('system', 'python/lib', 'swipl/lib/x86_64-linux'))
    loader = str(capsule / 'system/ld-linux-x86-64.so.2')
    command = [loader, '--inhibit-cache', '--library-path', library,
               str(capsule / 'swipl/bin/x86_64-linux/swipl'), '--stack-limit=64m',
               '-q', '-f', 'none', '--no-packs', '-s', str(capsule / 'bridge/worker.pl'),
               '--', 'silent']
    environment = {'PATH': '/nonexistent', 'HOME': os.getcwd(), 'TMPDIR': os.getcwd(),
                   'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                   'SWI_HOME_DIR': str(capsule / 'swipl'), 'PETTA_PATH': str(capsule / 'petta'),
                   'OMEGA_PATH': str(capsule / 'omega'), 'PYTHONHOME': str(capsule / 'python'),
                   'PYTHONPATH': str(capsule / 'bridge'), 'PYTHONNOUSERSITE': '1',
                   'PYTHONDONTWRITEBYTECODE': '1', 'LD_LIBRARY_PATH': library,
                   'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
    os.execve(loader, command, environment)


if __name__ == '__main__':
    main()
