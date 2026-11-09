#!/usr/bin/env python3
"""Persistent recovered-host JSON-lines endpoint for the desktop transport.

Requires ROKO_WORKSPACE_ROOT. No user request selects paths or executable code.
The workspace dependencies remain external, pinned, and unchanged.
"""
import os
from pathlib import Path
import shutil
import signal
import sys
import subprocess
import time


def main():
    root = Path(os.environ['ROKO_WORKSPACE_ROOT']).resolve(strict=True)
    source = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'symbolic-ai-v4/source'))
    from gateway import available, verify_inputs
    verify_inputs('541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0', time.monotonic()+60)
    if shutil.disk_usage(root).free < 4*1024**3 or available() < 7*1024**3:
        raise RuntimeError('Require 4GiB free disk and 7GiB available memory for startup')
    parent = os.getppid()
    def identity(pid):
        try:
            row = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            return None if row[0] == 'Z' else row[19]
        except OSError:
            return None
    parent_identity = identity(parent)
    if parent == 1 or parent_identity is None:
        raise RuntimeError('Parent lifetime binding failed')
    restored = root / 'recovery-second/runtime/swipl-basic/runtime'
    swi = restored / 'swipl/lib/swipl'
    python = restored / 'recovered-python312'
    system = root / 'symbolic-ai-v4/system'
    library = ':'.join(map(str, (system, python/'lib', swi/'lib/x86_64-linux')))
    environment = dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
        PYTHONHOME=str(python), PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1',
        PYTHONNOUSERSITE='1', LD_LIBRARY_PATH=library, SWI_HOME_DIR=str(swi),
        PETTA_PATH=str(root/'omega-baseline/vendor/PeTTa-omega-release'),
        OMEGA_PATH=str(root/'omega-baseline/vendor/PeTTa/repos/Omega'),
        ROKO_CONVERSATION_STEP=str(source/'step.metta'),
        ROKO_RECOVERED_PROFILE=str(root/'omega-baseline/recovery/granite-host-requalification'),
        ROKO_MODEL=str(root/'recovery-second/model/granite-4.0-h-tiny-Q4_K_M.gguf'),
        ROKO_PYTHON=sys.executable, ROKO_SYMBOLIC_ROOT=str(root/'symbolic-ai-v4'))
    command = [sys.executable, '-B', str(root/'omega-baseline/scripts/no-network.py'),
        str(system/'ld-linux-x86-64.so.2'), '--inhibit-cache', '--library-path', library,
        str(swi/'bin/x86_64-linux/swipl'), '--stack-limit=64m', '-q', '-f', 'none',
        '--no-packs', '-s', str(source/'worker.pl'), '--', 'silent']
    # no-network.py uses only stdlib/ctypes and execs the fixed matched loader.
    # Its Python process must use the current host interpreter environment first.
    # It sets the recovered ABI environment immediately before the final exec.
    os.environ['ROKO_MATCHED_ENV'] = __import__('json').dumps(environment)
    # A GUI may spawn us from a short-lived thread: PR_SET_PDEATHSIG would
    # incorrectly kill the session when that thread (not its process) exits.
    # Watch the parent's process start identity instead. The worker stays in our
    # process group; its separate native supervisor binds to the worker itself.
    stopping = []
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, lambda signum, frame: stopping.append(signum))
    child = subprocess.Popen([sys.executable, '-B', str(source/'recovered_exec.py'), *command[2:]])
    try:
        while child.poll() is None:
            if stopping or identity(parent) != parent_identity:
                child.terminate()
                try: child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                return 1
            time.sleep(.1)
        return child.returncode
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()

if __name__ == '__main__':
    sys.exit(main())
