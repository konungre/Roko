#!/usr/bin/env python3
"""Start a locally qualified fresh Omega/PeTTa/Granite JSON-lines session.

ROKO_FRESH_PROFILE is trusted administrator configuration, never request data.
The old recovered profile and its identity requirements are left unchanged.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from fresh import load_profile


def identity(pid):
    try:
        row = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return None if row[0]=='Z' else row[19]
    except OSError:
        return None


def main():
    source = Path(__file__).resolve().parent
    profile_path = str(Path(os.environ['ROKO_FRESH_PROFILE']).resolve(strict=True))
    profile = load_profile(profile_path)
    available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < 7*1024**3 or shutil.disk_usage(source).free < 4*1024**3:
        raise RuntimeError('Require 7GiB available memory and 4GiB free disk')
    parent = os.getppid()
    stamp = identity(parent)
    if parent == 1 or stamp is None:
        raise RuntimeError('Parent lifetime binding failed')
    environment = {'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8',
                   'PYTHONPATH':str(source), 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONNOUSERSITE':'1',
                   'PETTA_PATH':profile['petta'], 'OMEGA_PATH':profile['omega'],
                   'ROKO_CONVERSATION_STEP':str(source/'step.metta'),
                   'ROKO_FRESH_PROFILE':profile_path}
    environment.update(profile.get('runtime_env', {}))
    environment['PYTHONPATH'] = str(source) + os.pathsep + environment.get('PYTHONPATH', '')
    command = [profile['python'], '-B', str(source.parents[1]/'omega-baseline/scripts/no-network.py'),
               profile['swipl'], '--stack-limit=64m', '-q', '-f', 'none', '--no-packs',
               '-s', str(source/'worker.pl'), '--', 'silent']
    stopping = []
    for signum in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
        signal.signal(signum, lambda signum, frame: stopping.append(signum))
    child = subprocess.Popen([profile['python'], '-B', str(source/'fresh_exec.py'),
                              str(os.getpid()), identity(os.getpid()), *command],
                             env=environment)
    try:
        while child.poll() is None:
            if stopping or identity(parent) != stamp:
                # SWI's SIGTERM handler can finalize embedded Python while Janus
                # is inside communicate(), crashing Py_FinalizeEx. Cancellation
                # discards this entire session: kill the worker directly and let
                # its independent native subreaper observe parent death/clean up.
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
    raise SystemExit(main())
