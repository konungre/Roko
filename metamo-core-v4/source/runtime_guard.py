"""Current measured host closure, not a guest attestation or hostile-code sandbox."""
import hashlib
import json
from pathlib import Path
import sys
from paths import SWI, PYTHON, SYSTEM, MANIFEST

def runtime_maps():
    if tuple(sys.version_info[:3]) != (3, 12, 14):
        raise ValueError('Embedded Python ABI changed')
    with Path('/proc/self/maps').open('rb') as f:
        raw = f.read(131073)
    if not 1 <= len(raw) <= 131072:
        raise ValueError('Native map byte cap')
    paths = set()
    for line in raw.decode('utf-8', errors='strict').splitlines():
        fields = line.split(None, 5)
        if len(fields) < 2:
            raise ValueError('Malformed native map')
        if 'x' not in fields[1]:
            continue
        if len(fields) < 6 or fields[5].startswith('['):
            continue
        p = Path(fields[5])
        if not p.is_absolute() or not p.is_file() or str(p.resolve()) != str(p):
            raise ValueError('Unstable native executable map')
        if not any(p.is_relative_to(root) for root in (SWI,PYTHON,SYSTEM)):
            raise ValueError('Native executable escaped measured runtime roots')
        paths.add(str(p))
    required = {str(SWI/'bin/x86_64-linux/swipl'), str(SWI/'lib/x86_64-linux/janus.so'), str(PYTHON/'lib/libpython3.12.so.1.0')}
    if not required <= paths or not 3 <= len(paths) <= 64:
        raise ValueError('Missing native Python/SWI/Janus maps')
    lock = json.loads(MANIFEST.read_bytes())['files']
    for path in paths:
        row = lock.get(path)
        if row is None or not row['elf'] or hashlib.sha256(Path(path).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Unadmitted executable mapping')
    return {'python': [3,12,14], 'executable_mappings': sorted(paths)}
