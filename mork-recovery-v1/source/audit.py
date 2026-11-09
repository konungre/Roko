"""Read-only MORK restoration audit. Never launches, installs, or resolves crates."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import native_mork as adapter

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
SOURCE_PREFIX = 'mork-recovery-v1/private-sources/'
HISTORICAL_LOCK_SHA256 = '12fe7964128f3879a6066bb3d18a04d30a31a5c0274d54539171bf2ba7f02bbb'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        while block := source.read(1024 * 1024): h.update(block)
    return h.hexdigest()


def check_file(path, expected):
    path = Path(path)
    if not path.is_file(): return {'state': 'missing', 'expected_sha256': expected}
    actual = digest(path)
    return {'state': 'verified' if actual == expected else 'mismatch',
            'sha256': actual, 'expected_sha256': expected, 'bytes': path.stat().st_size}


def verify_sources(records, workspace=WORKSPACE):
    if type(records) is not list or not 1 <= len(records) <= 256:
        raise ValueError('Selected-source count outside audit bounds')
    paths = [r['path'] for r in records]
    if len(set(paths)) != len(paths): raise ValueError('Duplicate source record')
    total = 0
    for row in records:
        path = row['path']
        if not path.startswith(SOURCE_PREFIX) or '..' in Path(path).parts:
            raise ValueError('Source path outside private recovery tree')
        target = Path(workspace) / path
        if target.is_symlink() or target.resolve() != target.absolute():
            raise ValueError('Source symlink forbidden')
        if not target.is_file() or target.stat().st_size != row['bytes']:
            raise ValueError('Missing or resized source: ' + path)
        if not 0 <= row['bytes'] <= 1024**2: raise ValueError('Source size cap')
        total += row['bytes']
        if total > 8*1024**2: raise ValueError('Selected-source total cap')
        data = target.read_bytes()
        git = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if git != row['git_blob_sha'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Source hash mismatch: ' + path)
    return {'state': 'verified-selected-source', 'files': len(records), 'bytes': total}


def audit():
    manifest = ROOT / 'proof/verified-private-source.json'
    records = json.loads(manifest.read_bytes())['files']
    sources = verify_sources(records)
    ffi = adapter.ROOT / 'build-src/mork-stage/PeTTa/mork_ffi'
    runtime = {str(ffi/name): check_file(ffi/name, pin)
               for name, pin in adapter.PINNED_LIBRARIES.items()}
    expected_swi = adapter.ROOT / 'runtime/swipl/bin/swipl'
    runtime[str(expected_swi)] = check_file(expected_swi, adapter.SWIPL_SHA256)
    recovered_swi = WORKSPACE / 'recovery-second/runtime/swipl-basic/runtime/swipl/lib/swipl/bin/x86_64-linux/swipl'
    prerequisite = check_file(recovered_swi, adapter.SWIPL_SHA256)
    historical_lock = check_file(ffi/'Cargo.lock', HISTORICAL_LOCK_SHA256)
    baseline = {str(adapter.ROOT/relative): digest(adapter.ROOT/relative)
                for relative in ('MORK_STATUS.md', 'adapters/native_mork.py',
                                 'tests/test_native_mork.py', 'integration/native_mork.md')}
    return {
        'schema': 1, 'checked_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scope': 'Read-only source and runtime-byte inventory; no native execution',
        'selected_sources': sources, 'source_manifest_sha256': digest(manifest),
        'native_runtime': runtime, 'recovered_swi_prerequisite': prerequisite,
        'native_ready': False, 'native_checks_run': 0,
        'native_blocker': 'MORK shared objects and exact Cargo.lock/toolchain/registry closure absent; complete transitive runtime review required before launch',
        'historical_cargo_lock_sha256': HISTORICAL_LOCK_SHA256,
        'historical_lock': historical_lock,
        'historical_lock_restored': historical_lock['state'] == 'verified',
        'rustc_on_path': shutil.which('rustc'), 'cargo_on_path': shutil.which('cargo'),
        'disk_free_bytes': shutil.disk_usage(ROOT).free,
        'required_disk_reserve_bytes': 4*1024**3,
        'baseline_files_preserved': baseline,
        'redistribution': {'MORK': 'unverified; excluded', 'mork_ffi': 'unverified; excluded',
                           'PathMap': 'MIT at pinned source',
                           'gxhash': 'MIT at pinned source',
                           'tracking-allocator': 'MPL-2.0 at pinned source'},
        'limits': ['Selected source is not the whole repositories or a frozen Cargo closure',
                   'No replacement lock or historical binary hash has been fabricated',
                   'Sparse source snapshot uses nonexecutable local file modes',
                   'Historical native pass reports are not current qualification',
                   'No root image mounted, large archive copied, or toolchain installed'],
    }


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
