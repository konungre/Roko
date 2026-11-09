"""Observed executable mappings; acceptance belongs to the pinned host gate."""
from pathlib import Path
import sys


def runtime_maps():
    paths=set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields=line.split(maxsplit=5)
        if len(fields)==6 and 'x' in fields[1] and fields[5].startswith('/'):
            path=Path(fields[5])
            if not path.is_file():raise ValueError('Unresolvable executable mapping')
            paths.add(str(path.resolve()))
    return {'python':list(sys.version_info[:3]),'executable_mappings':sorted(paths)}
