"""Existing-runtime file mappings for a bounded PeTTa + SWI/Janus guest check.

Import file_mappings(root, python_base), then copy source to name with mode.
All destination names are relative to guest /. Symlinks deliberately dereference.
Base builder supplies CPython stdlib and approved libc/libm/ELF loader.
"""
from pathlib import Path

SWI_HOME = '/opt/roko/swipl'
PETTA_HOME = '/opt/roko/petta'
PYTHON_HOME = '/opt/roko/python'

def file_mappings(root, python_base):
    root, python_base = Path(root), Path(python_base)
    swi = root / 'runtime/swipl/lib/swipl'
    # Include the library search indexes and installed foreign libraries together.
    for source in sorted(swi.rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(swi)
        if rel.parts[0] not in {'bin', 'lib', 'library', 'boot.prc', 'swipl.home', 'ABI', 'LICENSE'}:
            continue
        yield source, 'opt/roko/swipl/' + str(rel), 0o755 if source.stat().st_mode & 0o111 else 0o644
    petta = root / 'vendor/PeTTa-omega-release'
    for subtree in ('src', 'lib'):
        for source in sorted((petta / subtree).rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts:
                yield source, 'opt/roko/petta/' + str(source.relative_to(petta)), 0o644
    yield petta / 'LICENSE', 'opt/roko/petta/LICENSE', 0o644
    yield python_base / 'lib/libpython3.12.so.1.0', 'opt/roko/python/lib/libpython3.12.so.1.0', 0o755
    # Supplemental dependencies of the already built SWI core and its extensions.
    for name in ('libgmp.so.10', 'libz.so.1', 'libcrypt.so.1', 'libpcre2-8.so.0'):
        source = root / 'boot/tooling/root/usr/lib/x86_64-linux-gnu' / name
        if not source.is_file():
            raise FileNotFoundError(source)
        yield source, 'lib/x86_64-linux-gnu/' + name, 0o755
    yield root / 'boot/userland/petta_smoke.pl', 'opt/roko/petta-smoke.pl', 0o644
    yield root / 'boot/userland/petta_smoke.sh', 'bin/petta-smoke', 0o755

    # Exact upstream Omega message-state subset, not the full autonomous entry point.
    omega = root / 'vendor/PeTTa/repos/Omega'
    for name in ('src/utils.py', 'src/loop.metta', 'LICENSE'):
        yield omega / name, 'opt/roko/omega/' + name, 0o644
