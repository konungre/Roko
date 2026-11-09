#!/usr/bin/env python3
"""Prepare only the small source overlay. Never compile, format, or launch a VM."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build-src/granite-guest-stage/source-v2'
PY_YAML = 'pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl'
PY_YAML_SHA = 'ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    files, origin = {}, {}

    def add(destination, data, source, expected=None):
        if expected is not None and sha(data) != expected:
            raise ValueError('Source pin mismatch: ' + source)
        files[destination] = data
        origin[destination] = {'source': source, 'sha256': sha(data), 'bytes': len(data)}

    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    omega = next(r for r in lock['repositories'] if r['path'] == 'vendor/PeTTa/repos/Omega')
    for relative in ('src/providers.py', 'src/config.py', 'LICENSE'):
        source = omega['path'] + '/' + relative
        add('opt/roko/' + source, (ROOT / source).read_bytes(), source, omega['files'][relative])
    wheel = ROOT / 'component-wheels' / PY_YAML
    if sha(wheel.read_bytes()) != PY_YAML_SHA:
        raise ValueError('Pinned PyYAML wheel changed')
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith('yaml/') and name.endswith('.py'):
                add('opt/roko/vendor/guest-python/' + name, archive.read(name), str(wheel.relative_to(ROOT)) + '!' + name)
            elif name.endswith('/licenses/LICENSE'):
                add('opt/roko/licenses/PyYAML-LICENSE', archive.read(name), str(wheel.relative_to(ROOT)) + '!' + name)
    data = (ROOT / 'scripts/roko.py').read_bytes()
    old_hash = sha(data)
    for before, after in (
        (b' import providers\n', b" sys.path.insert(0,str(ROOT/'vendor/guest-python'))\n import providers\n"),
        (b' from granite_pipe import GranitePipeProvider,ALLOWED\n', b' from granite_guest import GraniteGuestProvider as GranitePipeProvider,ALLOWED\n'),
        (b"],128,'none',[tool])", b"],64,'none',[tool])"),
    ):
        if data.count(before) != 1:
            raise ValueError('Exact CLI overlay anchor changed')
        data = data.replace(before, after)
    add('opt/roko/scripts/roko.py', data, 'scripts/roko.py with three explicit guest-only changes')
    origin['opt/roko/scripts/roko.py']['base_sha256'] = old_hash
    add('opt/roko/adapters/granite_guest.py', (HERE / 'granite_guest.py').read_bytes(), 'boot/granite-guest/granite_guest.py')
    model = json.loads((ROOT / 'granite-model.lock.json').read_text())
    if (model['bytes'] != 4230976352 or model['sha256'] != '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'):
        raise ValueError('Unexpected model pin')
    # No model, tokenizer, native binary, or new CPython is copied into the overlay.
    model['path'] = '/models/granite-4.0-h-tiny-Q4_K_M.gguf'
    add('opt/roko/granite-model.lock.json', (json.dumps(model, indent=2) + '\n').encode(), 'granite-model.lock.json with separate read-only disk path')
    runtime = {'status': 'source-only-not-built', 'files': {
        path.removeprefix('opt/roko/'): item['sha256'] for path, item in origin.items()},
        'native_binary_admission': 'pending; never infer ready from this source overlay'}
    add('opt/roko/granite-guest-runtime.lock.json', (json.dumps(runtime, indent=2) + '\n').encode(), 'explicit fail-closed placeholder')
    manifest = {
        'schema': 1, 'status': 'source-prepared-only', 'omega_commit': omega['commit'],
        'actual_omega_contract': ['providers.LLMRequest', 'providers.LLMProvider',
                                  'providers.registerLLMProvider', 'providers.llmProviderChat',
                                  'providers._validate_response', 'providers.llmResponseToSExpr'],
        'guest_python': '/usr/bin/python3.13 (existing official guest runtime)',
        'helper_source_files': {p.name: sha(p.read_bytes()) for p in (
            HERE / 'granite-guest.cpp', HERE / 'CMakeLists.txt', HERE / 'build-helper.sh')},
        'helper_llama_commit': 'f7591a6a01f9273de03331732bdc0b39721168be',
        'third_party_python': 'Pure-Python files from the already pinned PyYAML 6.0.3 wheel; no CPython-3.12 extension copied',
        'source_files': origin, 'source_bytes': sum(map(len, files.values())),
        'model_disk': {'path': 'build/granite-guest-model/model.ext4', 'format': 'ext4',
                       'image_bytes_planned': 4608 * 1024 * 1024,
                       'serial': 'roko-granite-model', 'label': 'ROKO_MODEL',
                       'uuid': '726f6b6f-6d6f-4465-8000-000000000001',
                       'qemu_read_only': True, 'mount': '/models',
                       'mount_options': ['ro', 'noload', 'nodev', 'nosuid', 'noexec'],
                       'model_bytes': model['bytes'], 'model_sha256': model['sha256'],
                       'formatted': False, 'image_sha256': None},
        'limits': {'threads': 1, 'context_tokens': 1024, 'input_tokens': 512,
                   'output_tokens': 64, 'physical_batch_tokens': 32,
                   'inference_seconds_native': 300, 'inference_seconds_provider': 310,
                   'asset_verification_seconds': 120, 'actions_dispatched': 0},
        'validation': {'static_only': True, 'native_helper_included': False,
                       'native_build_evidence': 'Separate from this source-only overlay; see results/granite-guest-build/binary-admission.json if present',
                       'python313_tested': False, 'memory_fit_measured': False,
                       'model_disk_created': False, 'guest_inference_executed': False},
    }
    return files, manifest


def stage(out=OUT):
    files, manifest = sources()
    out.mkdir(parents=True, exist_ok=False)
    for relative, data in files.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-source', action='store_true')
    args = parser.parse_args()
    manifest = stage() if args.stage_source else sources()[1]
    print(json.dumps(manifest, indent=2))
