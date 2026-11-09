#!/usr/bin/env python3
"""Static ELF inspection only; readelf never executes the inspected libraries."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'build-src/cognitive-capsule-guest/stage-v2/capsule/system'
LIBGCC = ROOT / 'boot/tooling/root/usr/lib/x86_64-linux-gnu/libgcc_s.so.1'
HASH = '30c61ab012a4241bed033725a09b61f5fdd3bb7df95ee852d0b096520524c7af'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readelf(path, flag):
    return subprocess.check_output(['readelf', flag, '--wide', str(path)], text=True, timeout=10)


def main():
    if LIBGCC.stat().st_size != 182856 or sha(LIBGCC) != HASH:
        raise ValueError('Approved libgcc bytes differ')
    lock = json.loads((ROOT / 'boot/tooling-packages.lock.json').read_text())
    package = next(p for p in lock['packages'] if p['package'] == 'libgcc-s1')
    if package['version'] != '14.2.0-19' or package['source'] != 'gcc-14' or sha(ROOT / package['file']) != package['sha256']:
        raise ValueError('Approved source/package pin differs')
    needed = readelf(LIBGCC, '--version-info')
    needs = needed.split("Version needs section", 1)[1]
    providers = {}
    provider = None
    for line in needs.splitlines():
        m = re.search(r'File: (\S+)', line)
        if m:
            provider = m[1]; providers[provider] = []
        m = re.search(r'Name: (GLIBC_\S+)', line)
        if m:
            providers[provider].append(m[1])
    definitions = {}; exported = set(); outputs = {'libgcc-versions.txt': needed}
    for name in ('libc.so.6', 'ld-linux-x86-64.so.2'):
        text = readelf(PRIVATE / name, '--version-info')
        definitions[name] = set(re.findall(r'Name: (GLIBC_\S+)', text.split('Version needs section')[0]))
        if not set(providers[name]) <= definitions[name]:
            raise ValueError('Private version definitions cannot satisfy libgcc: ' + name)
        symbols = readelf(PRIVATE / name, '--dyn-syms')
        for line in symbols.splitlines():
            if ' UND ' in line:
                continue
            m = re.search(r'\s([^\s@]+)@@?(GLIBC_\S+)', line)
            if m:
                exported.add((m[1], m[2]))
        outputs[name + '-versions.txt'] = text
    required = []
    for line in readelf(LIBGCC, '--dyn-syms').splitlines():
        if ' UND ' not in line:
            continue
        m = re.search(r'\s(\S+)@(GLIBC_\S+)', line)
        if m:
            required.append((m[1], m[2]))
    missing = sorted(set(required) - exported)
    if missing:
        raise ValueError('Private libc/loader missing required versioned symbols: ' + repr(missing))
    target = ROOT / 'results/cognitive-capsule-preparation/libgcc-static-v3'
    target.mkdir(mode=0o700, exist_ok=False)
    for name, data in outputs.items():
        (target / name).write_text(data)
    report = {'passed': True, 'method': 'readelf static metadata; no library execution',
              'library_sha256': HASH, 'library_bytes': 182856, 'package': package,
              'required_versions_by_provider': providers, 'required_versioned_symbols': required,
              'missing_versioned_symbols': missing,
              'private_provider_sha256': {name: sha(PRIVATE / name) for name in providers},
              'native_execution_performed': False}
    (target / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
