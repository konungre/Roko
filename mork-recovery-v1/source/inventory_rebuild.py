"""Inventory an explicitly built, trusted local candidate; never build or admit it.

Uses ldd only on caller-reviewed local build outputs and their linked libraries.
Do not point this utility at untrusted executables. Its output requires separate
host review; it is not an authenticity or sandbox claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def inventory(build_root):
    root = Path(build_root).resolve()
    ffi = root/'sources/PeTTa/mork_ffi'
    swi = root/'swipl-runtime'
    entry = {'ffi':str((ffi/'target/release/libmork_ffi.so').resolve()),
             'bridge':str((ffi/'morklib.so').resolve()),
             'swipl':str((swi/'bin/swipl').resolve())}
    dirs = [str(ffi/'target/release/deps'),
            str(root/'toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib'),
            str(swi/'lib/swipl/lib/x86_64-linux')]
    env = {**os.environ, 'LD_LIBRARY_PATH':os.pathsep.join(dirs)}
    files = {p.resolve() for p in swi.rglob('*') if p.is_file()}
    files.update(Path(p) for p in entry.values())
    files.add(Path(sys.executable).resolve())
    seccomp = Path('/usr/lib/x86_64-linux-gnu/libseccomp.so.2').resolve(strict=True)
    files.add(seccomp)
    pending = list(files)
    checked = set()
    while pending:
        path = pending.pop()
        if path in checked: continue
        checked.add(path)
        with path.open('rb') as handle:
            if handle.read(4) != b'\x7fELF': continue
        result = subprocess.run(['ldd',str(path)],env=env,text=True,capture_output=True,check=True)
        if 'not found' in result.stdout:
            raise RuntimeError('Unresolved native linkage: '+str(path)+'\n'+result.stdout)
        for line in result.stdout.splitlines():
            match = re.search(r'(?:=>\s*)?(/\S+)\s+\(',line)
            if match:
                target = Path(match[1]).resolve(strict=True)
                files.add(target)
                pending.append(target)
    return {'schema':'roko-private-mork-rebuild-v1', 'entrypoints':entry,
            'library_directories':dirs,
            'scope':'installed SWI files, entrypoints and observed ELF linkage; trusted host Python environment',
            'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('build_root')
    args=parser.parse_args()
    print(json.dumps(inventory(args.build_root),indent=2))
