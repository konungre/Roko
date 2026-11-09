"""Record fresh local native/import evidence; parent checks its pinned inventory."""
import hashlib
from pathlib import Path
import sys


def runtime_maps():
    maps=set();imports={}
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields=line.split(maxsplit=5)
        if len(fields)==6 and 'x' in fields[1] and fields[5].startswith('/'):
            p=Path(fields[5])
            if not p.is_file():raise ValueError('Missing executable map')
            maps.add(str(p.resolve()))
    for module in list(sys.modules.values()):
        if module is None:continue
        spec=getattr(module,'__spec__',None)
        if getattr(spec,'origin',None) in ('built-in','frozen'):continue
        name=getattr(module,'__file__',None)
        if name is None:continue
        p=Path(name)
        if not p.is_absolute() or p.suffix in ('.pyc','.pyo'):raise ValueError('Unexpected imported path')
        imports[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(python=list(sys.version_info[:3]),executable_mappings=sorted(maps),imported_files=imports,
        prefix=sys.prefix,base_prefix=sys.base_prefix,search_path=list(sys.path),
        flags={k:getattr(sys.flags,k) for k in ('isolated','no_site','no_user_site','dont_write_bytecode')})
