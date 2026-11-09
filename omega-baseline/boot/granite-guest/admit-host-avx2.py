#!/usr/bin/env python3
"""Admit the isolated AVX2 host helper; never claim guest portability."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/granite-host-avx2'
BINARY = ROOT / 'build/granite-host-avx2/omega-granite-host-avx2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*command):
    return subprocess.run(command, capture_output=True, text=True, timeout=10, check=True).stdout


def main():
    target = OUT / 'binary-admission.json'
    if target.exists():
        raise ValueError('Never overwrite binary admission')
    previous = json.loads((ROOT / 'results/granite-guest-build/binary-admission.json').read_text())
    for name, expected in previous['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Portable helper source changed: ' + name)
    if sha(ROOT / previous['binary']) != previous['binary_sha256']:
        raise ValueError('Portable helper changed')
    lock = json.loads((ROOT / 'granite-runtime.lock.json').read_text())
    for name, expected in lock['files'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Original runtime changed: ' + name)
    commands = json.loads((ROOT / 'build/llama/compile_commands.json').read_text())
    cpu_commands = [c for c in commands if '/ggml-cpu/' in c['file']]
    cpu_options = sorted({word for c in cpu_commands for word in shlex.split(c['command'])
                          if word.startswith('-m') or word == '-fopenmp'})
    expected_options = ['-fopenmp', '-mavx', '-mavx2', '-mbmi2', '-mf16c', '-mfma', '-msse4.2']
    if cpu_options != expected_options:
        raise ValueError('Unreviewed CPU build flags: ' + repr(cpu_options))
    required_flags = ['avx', 'avx2', 'bmi2', 'f16c', 'fma', 'sse4_2']
    cpu_text = Path('/proc/cpuinfo').read_text()
    processor_flags = [set(row.split(':', 1)[1].split()) for row in cpu_text.splitlines()
                       if row.startswith('flags')]
    if not processor_flags or not all(set(required_flags) <= flags for flags in processor_flags):
        raise ValueError('Visible CPU lacks required instruction support')
    dynamic = run('readelf', '-d', str(BINARY))
    runpaths = re.findall(r'\(RUNPATH\).*?\[(.*?)\]', dynamic)
    if runpaths != [str(ROOT / 'build/llama/bin')]:
        raise ValueError('Unexpected host-only RUNPATH')
    relocated_dir = ROOT / 'build/granite-host-avx2/relocated'
    relocated_dir.mkdir()
    relocated = relocated_dir / BINARY.name
    relocated.write_bytes(BINARY.read_bytes())
    relocated.chmod(0o555)
    smoke = subprocess.run([str(relocated)], cwd=relocated_dir,
                           env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                           capture_output=True, text=True, timeout=5)
    if smoke.returncode != 2 or 'expected --model' not in smoke.stderr:
        raise ValueError('Relocated host startup failed')
    ldd = run('ldd', str(relocated))
    if 'not found' in ldd:
        raise ValueError('Missing host runtime dependency')
    resolved = {}
    for line in ldd.splitlines():
        match = re.search(r'^\s*(\S+) => (/\S+)', line)
        if match:
            path = Path(match[2]).resolve()
            resolved[match[1]] = {'path': str(path), 'sha256': sha(path)}
            if match[1].startswith(('libggml', 'libllama')):
                relative = str(path.relative_to(ROOT))
                if lock['files'].get(relative) != sha(path):
                    raise ValueError('Unpinned resolved library')
    (OUT / 'elf-dynamic.txt').write_text(dynamic)
    (OUT / 'host-ldd.txt').write_text(ldd)
    (OUT / 'elf-versions.txt').write_text(run('readelf', '-V', str(BINARY)))
    report = {
        'status': 'host-only-avx2-binary-admitted',
        'binary': str(BINARY.relative_to(ROOT)), 'binary_sha256': sha(BINARY),
        'binary_bytes': BINARY.stat().st_size, 'llama_commit': lock['commit'],
        'native_source_sha256': previous['source_sha256']['boot/granite-guest/granite-guest.cpp'],
        'build_script_sha256': sha(ROOT / 'boot/granite-guest/build-host-avx2.sh'),
        'host_library_compile_commands_sha256': sha(ROOT / 'build/llama/compile_commands.json'),
        'host_library_cpu_compile_options': cpu_options, 'required_cpu_flags': required_flags,
        'host_all_visible_cpus_support_required_flags': True,
        'host_cpu_model': next(row.split(':', 1)[1].strip() for row in cpu_text.splitlines() if row.startswith('model name')),
        'host_visible_processors': len(processor_flags), 'resolved_host_libraries': resolved,
        'pinned_runtime_files': lock['files'],
        'elf_needed': re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic),
        'absolute_host_runpath': runpaths, 'relocated_binary_host_start': True,
        'relocation_caveat': 'Copied binary still depends on original absolute host library paths. Not self-contained or guest portable.',
        'portable_helper_unchanged': True, 'old_host_helper_unchanged': True,
        'threads': 1, 'openmp_compiled': True, 'omp_num_threads': 1,
        'runtime_repacking': False, 'library_repacking_compiled': True,
        'sampling': 'grammar then greedy, identical native source to generic baseline',
        'guest_admitted': False, 'model_loaded': False, 'default_model_changed': False,
    }
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
