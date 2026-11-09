#!/usr/bin/env python3
"""Stage a separate default-disabled raw provider and describe a tiny guest delta.

Never assembles a boot image, creates a raw fixture on disk, opens a model,
attaches a device, compiles code or starts a VM.
"""
import difflib
import hashlib
import json
from pathlib import Path
import stat

from synthetic import specification
from raw_transport import MODEL_BYTES, MODEL_SHA, TRANSPORT, capacity

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'build-src/granite-portable-stage/source-v2'
OUT = ROOT / 'build-src/granite-raw-block-stage/source-v1'
ROOT_ID = '32e03cfba11b02412dddd0a0a14c56b03a1290dcb5fa0e6710524b9f3ef78c80'
ROOT_SHA = '8fa91b7751abae9d16b4022402ac22b85cd308fa67810b809d4ad1f5d42ea03d'
BOOTSTRAP_SHA = '39f6595b65395110ab40912b9c14061a44347d9c0e10767033c9f1ed40acf614'
SOURCE_HOOK = b'$BB cp -a /newroot/usr/share/roko/root-seed/. /newroot/root/ || fail seed-home\n'
SWITCH_HOOK = b'exec /bin/busybox switch_root /newroot /usr/libexec/roko-session-init\n'
LIMIT = 2 * 1024**2


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_variants():
    original = (BASE / 'opt/roko/adapters/runtime_select.py').read_text()
    text = original.replace('import time\n', 'import time\nfrom raw_transport import admit_model\n', 1)
    start = text.index("    model = json.loads((root / 'granite-model.lock.json').read_text())")
    end = text.index('    proof = None\n', start)
    text = text[:start] + '''    provider._raw_model = admit_model(root, deadline)
    provider.model = provider._raw_model.helper_path
''' + text[end:]
    before = "'adapters/runtime_select.py', 'adapters/granite_guest.py'}"
    if text.count(before) != 1:
        raise ValueError('Runtime file-admission anchor changed')
    text = text.replace(before, "'adapters/runtime_select.py', 'adapters/granite_guest.py',\n                'adapters/raw_transport.py', 'granite-raw-transport.lock.json'}")
    provider_original = (BASE / 'opt/roko/adapters/granite_guest.py').read_text()
    before = '''    def start(self):
        start_runtime(self, verified_file)

    def stop(self):
        self.ready = False
'''
    after = '''    def start(self):
        self.stop()
        try:
            start_runtime(self, verified_file)
        except BaseException:
            self.stop()
            raise

    def stop(self):
        self.ready = False
        block = getattr(self, '_raw_model', None)
        if block is not None:
            block.close()
            self._raw_model = None
'''
    if provider_original.count(before) != 1:
        raise ValueError('Provider lifetime anchor changed')
    provider = provider_original.replace(before, after)
    return original, text, provider_original, provider


def stage():
    previous = json.loads((BASE / 'manifest.json').read_text())
    files = {}
    for name, item in previous['files'].items():
        path = BASE / name
        data = path.read_bytes()
        if sha(data) != item['sha256'] or len(data) != item['bytes']:
            raise ValueError('Pinned source stage changed: ' + name)
        files[name] = data
    original, variant, provider_original, provider = source_variants()
    files['opt/roko/adapters/runtime_select.py'] = variant.encode()
    files['opt/roko/adapters/granite_guest.py'] = provider.encode()
    files['opt/roko/adapters/raw_transport.py'] = (HERE / 'raw_transport.py').read_bytes()
    transport = {'transport': TRANSPORT, 'serial': 'roko-granite-model', 'source_bytes': MODEL_BYTES,
                 'capacity_bytes': capacity(MODEL_BYTES), 'sha256': MODEL_SHA,
                 'zero_tail_bytes': capacity(MODEL_BYTES) - MODEL_BYTES, 'logical_block_size': 512,
                 'status': 'awaiting-synthetic-proof-and-reviewed-admission',
                 'reviewed_admission': False, 'synthetic_receipt_sha256': None}
    files['opt/roko/granite-raw-transport.lock.json'] = (json.dumps(transport, indent=2) + '\n').encode()
    files.pop('opt/roko/granite-portable-runtime.lock.json')
    runtime = {'status': 'source-only-not-built', 'transport_variant': TRANSPORT,
               'optimized_loader_admitted': False, 'files': {k.removeprefix('opt/roko/'): sha(v) for k, v in files.items()},
               'system_files': {}, 'optimized_resolution': {},
               'limits': 'Runtime admission and separate raw transport admission are both required; neither is granted by source tests.'}
    files['opt/roko/granite-portable-runtime.lock.json'] = (json.dumps(runtime, indent=2) + '\n').encode()
    OUT.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
    manifest = {'status': 'source-only-not-built', 'regular_file_default_changed': False,
                'source_base': str(BASE.relative_to(ROOT)), 'source_base_manifest_sha256': sha((BASE / 'manifest.json').read_bytes()),
                'model_included': False, 'model_loaded': False, 'guest_booted': False,
                'native_binaries_included': False, 'source_bytes': sum(map(len, files.values())),
                'omega_commit': previous['omega_commit'],
                'files': {k: {'sha256': sha(v), 'bytes': len(v)} for k, v in files.items()}}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    diff = ''.join(difflib.unified_diff(original.splitlines(True), variant.splitlines(True), fromfile='regular-file-runtime-unchanged', tofile='explicit-raw-runtime'))
    diff += ''.join(difflib.unified_diff(provider_original.splitlines(True), provider.splitlines(True), fromfile='portable-provider-unchanged', tofile='explicit-raw-provider'))
    (OUT / 'source.diff').write_text(diff)
    return manifest


def tiny_delta():
    """Return small entries only. Existing accepted archive/root stay untouched."""
    archive = ROOT / 'build/disk-root-guest/bootstrap.cpio.gz'
    if sha(archive.read_bytes()) != BOOTSTRAP_SHA:
        raise ValueError('Accepted bootstrap archive changed')
    receipt = json.loads((ROOT / 'build/disk-root-guest/bootstrap.json').read_text())
    accepted = json.loads((ROOT / 'build/disk-root-guest/validation.json').read_text())
    if (receipt['build_id'] != ROOT_ID or not accepted['passed']
            or accepted['root_sha256'] != ROOT_SHA or accepted['build_id'] != ROOT_ID):
        raise ValueError('Accepted root receipt changed')
    original = (ROOT / 'boot/disk-root-guest/init.sh').read_bytes()
    if (sha(original) != receipt['entries']['init']['sha256']
            or original.count(SOURCE_HOOK) != 1 or original.count(SWITCH_HOOK) != 1):
        raise ValueError('Accepted bootstrap source/hook changed')
    init = original.replace(SOURCE_HOOK, b'$BB mkdir -m 700 /newroot/run/raw-model-probe || fail probe-dir\n'
                            b'$BB cp -a /raw-model-probe/. /newroot/run/raw-model-probe/ || fail probe-copy\n')
    init = init.replace(SWITCH_HOOK, b'exec /bin/busybox switch_root /newroot /run/raw-model-probe/init\n')
    shell = b'''#!/bin/sh
[ "$$" = 1 ] || exit 90
exec </dev/console >/dev/console 2>&1
export PATH=/usr/bin:/bin
cd /run/raw-model-probe || exit 91
if ! /bin/busybox sha256sum -c files.sha256; then
    echo ROKO_RAW_SYNTHETIC_HASH_FAILURE
    /bin/busybox poweroff -f
    while :; do /bin/busybox sleep 1; done
fi
/usr/bin/python3.13 -I /run/raw-model-probe/entry.py
rc=$?
echo ROKO_RAW_SYNTHETIC_EXIT "$rc"
/bin/busybox poweroff -f
while :; do /bin/busybox sleep 1; done
'''
    # Isolated Python disables environment paths; only this verified tiny directory
    # is explicitly added for its local stdlib-only imports.
    entry = b"import runpy, sys\nsys.path.insert(0, '/run/raw-model-probe')\nrunpy.run_path('/run/raw-model-probe/guest_probe.py', run_name='__main__')\n"
    values = {name: ((HERE / name).read_bytes(), 0o444) for name in ('raw_transport.py', 'synthetic.py', 'guest_probe.py')}
    values['init'] = (shell, 0o755)
    values['entry.py'] = (entry, 0o444)
    values['synthetic.lock.json'] = ((json.dumps(specification(), sort_keys=True) + '\n').encode(), 0o444)
    sums = ''.join(sha(data) + '  ' + name + '\n' for name, (data, _) in sorted(values.items())).encode()
    values['files.sha256'] = (sums, 0o444)
    entries = {'raw-model-probe': (b'', stat.S_IFDIR | 0o700, 0, 0), 'init': (init, stat.S_IFREG | 0o755, 0, 0)}
    for name, (data, mode) in values.items():
        entries['raw-model-probe/' + name] = (data, stat.S_IFREG | mode, 0, 0)
    total = sum(len(item[0]) for item in entries.values())
    if total > LIMIT:
        raise ValueError('Tiny synthetic delta exceeds 2 MiB')
    plan = {'status': 'source-prepared-not-booted', 'root_build_id': ROOT_ID, 'root_sha256': ROOT_SHA,
            'base_bootstrap_sha256': BOOTSTRAP_SHA, 'delta_payload_bytes': total,
            'root_rehashed_this_step': False, 'fixture': specification(), 'fixture_materialized': False,
            'vm': {'memory_mib': 512, 'cpus': 1, 'acceleration': 'tcg', 'network': 'none',
                   'display': 'none', 'wall_seconds': 120, 'whole_process_group_kill': True},
            'reserved_host_free_disk_bytes': 4 * 1024**3, 'model_attached': False,
            'entries': {n: {'sha256': sha(x[0]), 'bytes': len(x[0]), 'mode': x[1]} for n, x in entries.items()},
            'pending': ['Reviewed source and coordinated lane grant', 'Bootstrap derivative assembly and inert fixture materialization',
                        'O_RDONLY host FD admission and actual packaged QEMU/kernel synthetic guest proof',
                        'Host after-shutdown inode/hash unchanged proof', 'Separate reviewed model/runtime admission']}
    return entries, plan


if __name__ == '__main__':
    report = stage()
    _, plan = tiny_delta()
    results = ROOT / 'results/granite-raw-block-preparation'
    results.mkdir(exist_ok=True)
    (results / 'source-stage.json').write_text(json.dumps(report, indent=2) + '\n')
    (results / 'synthetic-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'source_bytes': report['source_bytes'], 'delta_payload_bytes': plan['delta_payload_bytes'],
                      'status': plan['status'], 'fixture': plan['fixture']}, indent=2))
