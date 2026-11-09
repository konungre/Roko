#!/usr/bin/env python3
"""Separate threading-only candidate based on the admitted 900-second guest."""
import difflib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'boot/granite-model-guest-extended'))
import prepare_extended as previous
sha = previous.sha
synthetic_proof = previous.synthetic_proof
RECEIPT_SHA = previous.RECEIPT_SHA
OUT = ROOT / 'build-src/granite-model-guest-stage/candidate-v4-fourcore'
BUILD = ROOT / 'build/granite-model-fourcore-helper'


def source():
    before = (previous.BUILD / 'granite-guest-900.cpp').read_text()
    after = before
    for old, new in [('context.n_threads = 1;', 'context.n_threads = 4;'),
                     ('context.n_threads_batch = 1;', 'context.n_threads_batch = 4;'),
                     ('repack=0 threads=1\\n', 'repack=0 threads=4\\n')]:
        after = previous.replace_once(after, old, new)
    return before, after


def validate():
    before, after = source()
    if (BUILD / 'granite-guest-900-fourcore.cpp').read_text() != after:
        raise ValueError('Unexpected four-thread native source')
    old = json.loads((previous.OUT / 'manifest.json').read_text())
    for name, expected in old['static_link_inputs'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('Pinned static link input changed: ' + name)
    shared = json.loads((ROOT / 'granite-runtime.lock.json').read_text())['files']
    for name, expected in shared.items():
        if name.startswith('build/llama/bin/') and sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('Pinned shared link input changed: ' + name)
    new = json.loads((OUT / 'manifest.json').read_text())
    allowed = {'adapters/granite_guest.py', 'runtime/granite/generic/infer',
               'runtime/granite/avx2/infer', 'granite-portable-runtime.lock.json'}
    changed = {name for name in old['files'] if old['files'][name]['sha256'] != new['files'][name]['sha256']}
    if changed != allowed or set(old['files']) != set(new['files']):
        raise ValueError('Unexpected candidate file changes')
    for name, pin in new['files'].items():
        data = (OUT / 'roko' / name).read_bytes()
        if sha(data) != pin['sha256'] or len(data) != pin['bytes']:
            raise ValueError('Four-core candidate changed: ' + name)
    old_provider = (previous.OUT / 'roko/adapters/granite_guest.py').read_text()
    if (OUT / 'roko/adapters/granite_guest.py').read_text() != previous.replace_once(old_provider, "'OMP_NUM_THREADS': '1'", "'OMP_NUM_THREADS': '4'"):
        raise ValueError('Provider change exceeds thread environment')
    old_request = (previous.HERE / 'guest_request.py').read_text()
    if (HERE / 'guest_request.py').read_text() != previous.replace_once(old_request, "'native_threads': 1", "'native_threads': 4"):
        raise ValueError('Fixture change exceeds thread metadata')
    return new


def main():
    if OUT.exists() or BUILD.exists():
        raise ValueError('Four-core candidate already exists; preserve it')
    before, after = source()
    BUILD.mkdir(mode=0o700)
    src = BUILD / 'granite-guest-900-fourcore.cpp'
    src.write_text(after)
    (BUILD / 'source.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='one-thread-900s', tofile='four-thread-900s')))
    prior = json.loads((previous.OUT / 'manifest.json').read_text())
    commands = {}
    for backend in ('generic', 'avx2'):
        command = [str(src) if arg == str(previous.BUILD / 'granite-guest-900.cpp') else
                   str(BUILD / (backend + '-infer')) if arg == str(previous.BUILD / (backend + '-infer')) else arg
                   for arg in prior['commands'][backend]]
        built = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
        (BUILD / (backend + '-build.txt')).write_text(built.stdout + built.stderr)
        commands[backend] = command
    files = {}
    for name, pin in prior['files'].items():
        data = (previous.OUT / 'roko' / name).read_bytes()
        if sha(data) != pin['sha256'] or len(data) != pin['bytes']:
            raise ValueError('Prior candidate changed')
        files[name] = data
    files['adapters/granite_guest.py'] = previous.replace_once(files['adapters/granite_guest.py'].decode(), "'OMP_NUM_THREADS': '1'", "'OMP_NUM_THREADS': '4'").encode()
    for backend in ('generic', 'avx2'):
        files[f'runtime/granite/{backend}/infer'] = (BUILD / (backend + '-infer')).read_bytes()
    runtime = json.loads(files['granite-portable-runtime.lock.json'])
    runtime['files'] = {name: sha(data) for name, data in files.items() if name != 'granite-portable-runtime.lock.json'}
    files['granite-portable-runtime.lock.json'] = (json.dumps(runtime, indent=2) + '\n').encode()
    OUT.mkdir(mode=0o700)
    for name, data in files.items():
        path = OUT / 'roko' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(prior['files'][name]['mode'])
    (HERE / 'guest_request.py').write_text(previous.replace_once((previous.HERE / 'guest_request.py').read_text(), "'native_threads': 1", "'native_threads': 4"))
    report = {'status': 'prepared-threading-only-awaiting-lane',
              'parent_manifest_sha256': sha((previous.OUT / 'manifest.json').read_bytes()),
              'model_read': False, 'native_source_before_sha256': sha(before.encode()),
              'native_source_after_sha256': sha(after.encode()), 'commands': commands,
              'bounds': dict(prior['bounds'], tcg_cpus=4, native_threads=4),
              'payload_bytes': sum(map(len, files.values())),
              'files': {name: {'sha256': sha(data), 'bytes': len(data), 'mode': prior['files'][name]['mode']} for name, data in files.items()}}
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    validate()
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','commands')},indent=2))

if __name__ == '__main__': main()
