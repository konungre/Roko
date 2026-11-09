"""Current measured host closure, not a guest attestation or hostile-code sandbox."""
import hashlib
import json
from pathlib import Path
import sys
from paths import PYTHON, SYSTEM, MANIFEST, PYTHON_BINARY, HERE, UPSTREAM

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
        if not any(p.is_relative_to(root) for root in (PYTHON,SYSTEM)):
            raise ValueError('Native executable escaped measured runtime roots')
        paths.add(str(p))
    required = {str(PYTHON_BINARY)}
    if not required <= paths or not 2 <= len(paths) <= 64:
        raise ValueError('Missing measured Python executable maps')
    lock = json.loads(MANIFEST.read_bytes())['files']
    for path in paths:
        row = lock.get(path)
        if row is None or not row['elf'] or hashlib.sha256(Path(path).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Unadmitted executable mapping')
    return {'python': [3,12,14], 'executable_mappings': sorted(paths), 'imports': import_proof(json.loads(MANIFEST.read_bytes()))}


def validate_import_proof(proof,lock):
    expected_paths=[str(HERE),str(PYTHON/'lib/python312.zip'),str(PYTHON/'lib/python3.12'),str(PYTHON/'lib/python3.12/lib-dynload')]
    expected_flags={'safe_path':True,'no_user_site':1,'no_site':1,'dont_write_bytecode':1}
    if type(proof) is not dict or set(proof)!={'prefix','exec_prefix','base_prefix','base_exec_prefix','search_path','flags','imported_files'}:raise ValueError('Import proof schema')
    if any(proof[k]!=str(PYTHON) for k in ('prefix','exec_prefix','base_prefix','base_exec_prefix')):raise ValueError('Recovered Python prefix binding')
    if proof['search_path']!=expected_paths or json.dumps(proof['flags'],sort_keys=True)!=json.dumps(expected_flags,sort_keys=True):raise ValueError('Python search path/isolation flags changed')
    files=proof['imported_files']
    if type(files) is not dict or not 1<=len(files)<=192:raise ValueError('Import file count')
    for path,h in files.items():
        if type(path) is not str or path not in lock['files'] or not any(Path(path).is_relative_to(r) for r in (HERE,UPSTREAM,PYTHON)) or lock['files'][path]['sha256']!=h:raise ValueError('Unadmitted Python import file')
    for p in (HERE/'contract.py',HERE/'experiment.py',HERE/'runtime_guard.py',HERE/'paths.py',PYTHON/'lib/python3.12/json/__init__.py',PYTHON/'lib/python3.12/logging/__init__.py'):
        if str(p) not in files:raise ValueError('Required Python import provenance missing')
    return proof

def import_proof(lock):
    files={}
    for module in list(sys.modules.values()):
        if module is None:continue
        spec=getattr(module,'__spec__',None);origin=getattr(spec,'origin',None)
        if origin in ('built-in','frozen'):continue
        path=getattr(module,'__file__',None)
        if path is None:continue
        p=Path(path)
        if not p.is_absolute() or p.resolve()!=p or p.suffix in ('.pyc','.pyo'):raise ValueError('Unstable Python import path')
        row=lock['files'].get(str(p))
        if row is None or not any(p.is_relative_to(r) for r in (HERE,UPSTREAM,PYTHON)):raise ValueError('Python imported outside admitted closure')
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h!=row['sha256']:raise ValueError('Imported Python bytes changed')
        files[str(p)]=h
    proof={k:getattr(sys,k) for k in ('prefix','exec_prefix','base_prefix','base_exec_prefix')}
    proof.update(search_path=list(sys.path),flags={k:getattr(sys.flags,k) for k in ('safe_path','no_user_site','no_site','dont_write_bytecode')},imported_files=files)
    return validate_import_proof(proof,lock)
