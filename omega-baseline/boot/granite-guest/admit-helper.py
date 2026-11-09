#!/usr/bin/env python3
"""Audit the built candidate without loading a model or booting a guest."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/granite-guest-helper'
BINARY = BUILD / 'omega-granite-guest'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readelf(*args):
    return subprocess.run(['readelf', *map(str, args)], capture_output=True, text=True,
                          check=True, timeout=10).stdout


def admit():
    commands = json.loads((BUILD / 'compile_commands.json').read_text())
    for entry in commands:
        command = entry['command']
        if re.search(r'-m(?:arch=native|cpu=native|avx\S*|fma|f16c|sse4\S*|bmi\S*|amx\S*)\b', command):
            raise ValueError('Non-generic CPU flag: ' + command)
        if '-march=x86-64' not in command or '-mtune=generic' not in command:
            raise ValueError('Missing explicit generic target')
    cache = (BUILD / 'CMakeCache.txt').read_text()
    for flag in ('NATIVE', 'BACKEND_DL', 'CPU_REPACK', 'SSE42', 'AVX', 'AVX2', 'FMA',
                 'F16C', 'OPENMP', 'CUDA', 'VULKAN', 'BLAS', 'LLAMAFILE'):
        if f'GGML_{flag}:BOOL=OFF' not in cache:
            raise ValueError('Unexpected CMake feature: ' + flag)
    dynamic = readelf('-d', BINARY)
    if re.search(r'RPATH|RUNPATH|libllama|libggml', dynamic):
        raise ValueError('Non-relocatable helper')
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic)
    if not set(needed) <= {'libstdc++.so.6', 'libgcc_s.so.1', 'libc.so.6', 'libm.so.6'}:
        raise ValueError('Unexpected binary dependency')
    stage = ROOT / 'build-src/basilisk-stage'
    sysroot = stage / 'sysroot'
    records = {r['path']: r for r in json.loads((stage / 'debian-files.lock.json').read_text())['files']}
    guest_libraries = {}
    for name in needed:
        path = sysroot / 'usr/lib/x86_64-linux-gnu' / name
        resolved = path.resolve()
        relative = str(resolved.relative_to(sysroot.resolve()))
        if records[relative]['kind'] != 'file' or sha(resolved) != records[relative]['sha256']:
            raise ValueError('Guest library does not match signed-source lock')
        guest_libraries[name] = {'path': relative, 'sha256': sha(resolved),
                                 'versions': set(re.findall(r'Name: (\S+)', readelf('-V', resolved)))}
    version_info = readelf('-V', BINARY)
    needs_section = version_info.split('Version needs section', 1)[1]
    current = None
    required = {}
    for line in needs_section.splitlines():
        file_match = re.search(r'File: (\S+)', line)
        if file_match:
            current = file_match[1]
            required.setdefault(current, [])
        name_match = re.search(r'Name: (\S+)', line)
        if name_match and current:
            version = name_match[1]
            if version not in guest_libraries[current]['versions']:
                raise ValueError('Guest ABI cannot satisfy ' + current + ':' + version)
            required[current].append(version)
    for item in guest_libraries.values():
        del item['versions']
    relocated = ROOT / 'build/granite-guest-relocated'
    relocated.mkdir(exist_ok=True)
    target = relocated / BINARY.name
    if target.exists() and sha(target) != sha(BINARY):
        raise ValueError('Relocated binary already exists with other content')
    if not target.exists():
        target.write_bytes(BINARY.read_bytes())
        target.chmod(0o555)
    result = subprocess.run([str(target)], cwd=relocated, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 2 or 'expected --model' not in result.stderr:
        raise ValueError('Relocated helper did not start normally')
    # Also start with the existing official guest loader and its library directory.
    loader = sysroot / 'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
    result_guest = subprocess.run([str(loader), '--library-path', str(loader.parent), str(target)],
                                 cwd=relocated, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                                 capture_output=True, text=True, timeout=5)
    if result_guest.returncode != 2 or 'expected --model' not in result_guest.stderr:
        raise ValueError('Guest library relocation smoke failed')
    return {'status': 'host-binary-admitted-not-guest-tested', 'binary': str(BINARY.relative_to(ROOT)),
            'binary_sha256': sha(BINARY), 'binary_bytes': BINARY.stat().st_size,
            'llama_commit': 'f7591a6a01f9273de03331732bdc0b39721168be',
            'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (
                ROOT / 'boot/granite-guest/granite-guest.cpp', ROOT / 'boot/granite-guest/CMakeLists.txt')},
            'compile_commands_sha256': sha(BUILD / 'compile_commands.json'),
            'generic_compile_entries': len(commands), 'elf_needed': needed,
            'elf_required_versions': required, 'guest_libraries': guest_libraries,
            'no_rpath': True, 'relocated_host_start': True, 'relocated_guest_library_start': True,
            'model_loaded': False, 'guest_booted': False}


if __name__ == '__main__':
    print(json.dumps(admit(), indent=2))
