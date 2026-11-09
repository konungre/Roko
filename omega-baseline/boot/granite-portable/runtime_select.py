"""CPU-only bounded runtime selection. Missing CPU proof selects generic."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

REQUIRED = ('avx', 'avx2', 'bmi2', 'f16c', 'fma', 'sse4_2', 'os_avx_state')
LIBRARIES = ('libllama.so.0', 'libggml.so.0', 'libggml-base.so.0', 'libggml-cpu.so.0', 'libgomp.so.1')
LOADER = '/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
SYSTEM = '/usr/lib/x86_64-linux-gnu'


def choose(proof, optimized_admitted):
    valid = (isinstance(proof, dict) and proof.get('architecture') == 'x86_64'
             and proof.get('all_allowed_cpus') is True
             and type(proof.get('tested_cpus')) is int and 0 < proof['tested_cpus'] <= 1024
             and all(proof.get(key) is True for key in REQUIRED))
    return 'avx2' if optimized_admitted is True and valid else 'generic'


def parent_start():
    return int(Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19])


def supervised_prefix(root, native):
    return [sys.executable, str(root / 'runtime/granite/supervise.py'),
            '--parent-pid', str(os.getpid()), '--parent-start', str(parent_start()),
            '--seconds', '300', '--', *native]


def stop_supervisor(proc):
    if proc.poll() is None:
        # Give the subreaper time to clean escaped descendants. Never kill caller group.
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)


def loader_command(root):
    lib = root / 'runtime/granite/avx2/lib'
    helper = root / 'runtime/granite/avx2/infer'
    # Exact source library bytes retain old RUNPATH metadata. Explicit precedence
    # and a checked --list closure are mandatory; no host path may resolve.
    ignored = ':'.join([str(helper), *LIBRARIES, *(str(lib / n) for n in LIBRARIES)])
    return [LOADER, '--inhibit-cache', '--glibc-hwcaps-mask', '', '--inhibit-rpath', ignored,
            '--library-path', str(lib) + ':' + SYSTEM, str(helper)]


def resolved_paths(output):
    result = {}
    for line in output.splitlines():
        if 'not found' in line:
            raise ValueError('Missing native dependency')
        match = re.match(r'\s*(\S+) => (/\S+)', line)
        if match:
            name = Path(match[1]).name
            if name in result:
                raise ValueError('Duplicate loader dependency')
            result[name] = match[2]
        elif 'linux-vdso.so.1' in line:
            continue
        else:
            match = re.match(r'\s*(/\S+)\s+\(', line)
            if match:
                result[Path(match[1]).name] = match[1]
            elif line.strip():
                raise ValueError('Unrecognized loader diagnostic')
    return result


def start_runtime(provider, verified_file):
    provider.ready = False
    root = provider.root
    deadline = time.monotonic() + 120
    manifest = json.loads((root / 'granite-portable-runtime.lock.json').read_text())
    if manifest.get('status') != 'guest-runtime-admitted':
        raise ValueError('Portable guest runtime awaits binary and loader admission')
    files = manifest['files']
    required = {'runtime/granite/generic/infer', 'runtime/granite/supervise.py',
                'adapters/runtime_select.py', 'adapters/granite_guest.py'}
    if not required <= set(files):
        raise ValueError('Incomplete runtime manifest')
    for relative, expected in files.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != relative:
            raise ValueError('Unsafe runtime path')
        verified_file(root / path, expected, deadline)
    for path, expected in manifest['system_files'].items():
        if not path.startswith(SYSTEM + '/'):
            raise ValueError('Unexpected guest system dependency')
        verified_file(Path(path), expected, deadline)
    model = json.loads((root / 'granite-model.lock.json').read_text())
    if (model['path'] != '/models/granite-4.0-h-tiny-Q4_K_M.gguf'
            or model['sha256'] != '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
            or model['bytes'] != 4230976352):
        raise ValueError('Unexpected model pin')
    provider.model = Path(model['path'])
    if provider.model.stat().st_size != model['bytes']:
        raise ValueError('Wrong model size')
    mounts = [row.split() for row in Path('/proc/self/mountinfo').read_text().splitlines()]
    if not any(len(row)>5 and row[4]=='/models' and 'ro' in row[5].split(',') for row in mounts):
        raise ValueError('Separate model mount must be read-only')
    verified_file(provider.model, model['sha256'], deadline)
    proof = None
    probe = 'runtime/granite/cpuid-probe'
    if probe in files:
        try:
            result = subprocess.run([str(root / probe)], capture_output=True, timeout=3, check=True)
            if len(result.stdout)>4096 or len(result.stderr)>4096:
                raise ValueError('CPU probe output limit')
            proof = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            proof = None
    provider.backend = choose(proof, manifest.get('optimized_loader_admitted'))
    provider.command_prefix = [str(root / 'runtime/granite/generic/infer')]
    if provider.backend == 'avx2':
        need = {'runtime/granite/avx2/infer', *(f'runtime/granite/avx2/lib/{n}' for n in LIBRARIES)}
        if not need <= set(files):
            raise ValueError('Incomplete optimized runtime')
        provider.command_prefix = loader_command(root)
        probe_cmd = provider.command_prefix[:-1] + ['--list', provider.command_prefix[-1]]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5, check=True,
                                env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        if len(result.stdout)>16384 or result.stderr:
            raise ValueError('Unexpected loader diagnostic')
        actual = resolved_paths(result.stdout)
        expected = manifest['optimized_resolution']
        if actual != expected:
            raise ValueError('Unadmitted native library resolution')
    provider.ready = True
