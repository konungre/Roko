#!/usr/bin/env python3
"""Read/hash existing files and freeze a separate128MiB capsule candidate.

Does not run source from the capsule, native binaries, compilers, VMs or models.
Does not change any old lock, stage, root image or model20MiB payload cap.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build-src/cognitive-capsule-guest/stage-v4'
PREVIOUS = ROOT / 'build-src/cognitive-capsule-guest/stage-v3'
CAP = 128 * 1024**2
RESERVE = 4 * 1024**3
PINS = {'petta': '7037f4c2ad378c52fc328004fe216d5118b674f0',
        'omega': '21d8634b57deb45df3d5bcbb144cf4b314793f14',
        'swipl': '69e12af81c17ae5925f7555234c6575adf3a1e85',
        'janus': 'a751822dc7eae86af873ddba41b255ae820698fe'}
KEY_HASHES = {'capsule/swipl/lib/x86_64-linux/janus.so': '9299db5d318ff644f600e830d20acbc315de1050f9091884b82db3463f2d7414',
              'capsule/swipl/lib/x86_64-linux/libswipl.so.10.0.2': 'ef908d2e42584c4115536a07a8eccda4cdc4fc3d85d621d91a3b6a28634beab5',
              'capsule/python/lib/libpython3.12.so.1.0': '7e177a680eabb11fcb7d3867f7a1b9c4b93a9bd5b18129ce1af51ec07977b024',
              'capsule/omega/src/loop.metta': '4245a23036c434bde33946169fbe71bff0b9cef955476f104f0399c3ce6655d6',
              'capsule/omega/src/utils.py': '32eb58e9f34fb19b06a5f4ae0940aa0efbdfd550b5cc4d8345e01d8598a3e1d4'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf_metadata(data):
    """Inspect little-endian ELF64 metadata without invoking readelf/ldd/loader."""
    if data[:4] != b'\x7fELF':
        return None
    if data[4:6] != b'\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 62:
        raise ValueError('Expected little-endian x86_64 ELF64')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    loads, dynamic, interpreter = [], None, None
    for i in range(count):
        kind, flags, off, va, pa, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', data, offset + i * size)
        if off + filesz > len(data):
            raise ValueError('ELF segment extends past input')
        if kind == 1:
            loads.append((va, off, filesz))
        elif kind == 2:
            dynamic = (off, filesz)
        elif kind == 3:
            interpreter = data[off:off + filesz].rstrip(b'\0').decode()
    if dynamic is None:
        return {'needed': [], 'interpreter': interpreter, 'runpath': []}
    tags = []
    for pos in range(dynamic[0], sum(dynamic), 16):
        tag, value = struct.unpack_from('<qQ', data, pos)
        if tag == 0:
            break
        tags.append((tag, value))
    address = next((v for t, v in tags if t == 5), None)
    strsize = next((v for t, v in tags if t == 10), 0)
    found = [off + address - va for va, off, size in loads if address is not None and va <= address < va + size]
    if len(found) != 1:
        raise ValueError('Missing or ambiguous ELF dynamic string table')
    start = found[0]
    def string(index):
        if index >= strsize:
            raise ValueError('ELF string index outside table')
        end = data.find(b'\0', start + index, start + strsize)
        if end < 0:
            raise ValueError('Unterminated ELF dynamic string')
        return data[start + index:end].decode()
    return {'needed': [string(v) for t, v in tags if t == 1],
            'interpreter': interpreter, 'runpath': [string(v) for t, v in tags if t in (15, 29)]}


def replace_once(data, before, after):
    if data.count(before) != 1:
        raise ValueError('Controller exact transformation anchor changed')
    return data.replace(before, after)


def cli_variant(data):
    data = replace_once(data, b" args=p.parse_args(argv)\n", b''' cognition=sub.add_parser('cognition');cognition.add_argument('task');cognition.add_argument('--evidence',required=True)
 args=p.parse_args(argv)
''')
    data = replace_once(data, b"active=args.command in ('infer','check','attention')", b"active=args.command in ('infer','check','attention','cognition')")
    data = replace_once(data, b"  elif args.command=='infer':\n", b'''  elif args.command=='cognition':
   from guest_cognition import run_and_verify,CognitiveError
   state.clear_proposal()
   revision=store.save(state,expected_revision=revision)
   try:extra=run_and_verify(state,revision,args.evidence,ROOT.parent,ROOT.parent/'admission.json')
   except CognitiveError as error:
    print(json.dumps({'cognition_error':str(error),'receipt':error.receipt}),file=sys.stderr)
    raise
  elif args.command=='infer':
''')
    data = replace_once(data, b"'infer':'review','close':'complete'", b"'infer':'review','cognition':'review','close':'complete'")
    data = replace_once(data, b'create, evidence, infer, propose, check, close, show, list, status, packages, attention.', b'create, evidence, cognition, infer, propose, check, close, show, list, status, packages, attention.')
    return data


def inputs():
    lock_path = ROOT / 'boot/guest-userland-files.lock.json'
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)['files']
    rows = {}
    for old, pin in lock.items():
        if old.startswith(('opt/roko/python/', 'opt/roko/swipl/', 'opt/roko/petta/', 'opt/roko/omega/')):
            name = 'capsule/' + old.removeprefix('opt/roko/')
        elif old.startswith(('lib/x86_64-linux-gnu/', 'lib64/')):
            name = 'capsule/system/' + Path(old).name
        elif old.startswith('licenses/'):
            name = old
        else:
            continue
        source = Path(pin['source'])
        data = source.read_bytes()
        if sha(data) != pin['sha256']:
            raise ValueError('Existing locked input changed: ' + old)
        mode = 0o555 if source.stat().st_mode & 0o111 else 0o444
        rows[name] = (data, mode, {'source': str(source), 'old_guest_path': old})
    # Runtime-attested dynamic unwinder dependency from preserved attempt1.
    # Exact parent-approved existing Debian bytes; no ambient fallback allowed.
    libgcc = root_libgcc = 'usr/lib/x86_64-linux-gnu/libgcc_s.so.1'
    libgcc_source = ROOT / 'boot/tooling/root' / libgcc
    libgcc_data = libgcc_source.read_bytes()
    libgcc_hash = '30c61ab012a4241bed033725a09b61f5fdd3bb7df95ee852d0b096520524c7af'
    tooling = json.loads((ROOT / 'boot/tooling-files.lock.json').read_text())['files'][libgcc]
    current_root = json.loads((ROOT / 'build/disk-root-guest/root-source.json').read_text())['entries'][root_libgcc]
    abi_proof = json.loads((ROOT / 'results/cognitive-capsule-preparation/libgcc-static-v3/validation.json').read_text())
    if len(libgcc_data) != 182856 or sha(libgcc_data) != libgcc_hash or tooling['sha256'] != libgcc_hash or current_root['sha256'] != libgcc_hash or abi_proof['passed'] is not True or abi_proof['library_sha256'] != libgcc_hash:
        raise ValueError('Approved dynamic libgcc closure or ABI proof differs')
    for name, expected in abi_proof['private_provider_sha256'].items():
        if sha(rows['capsule/system/' + name][0]) != expected:
            raise ValueError('Private GLIBC provider changed after symbol review')
    rows['capsule/system/libgcc_s.so.1'] = (libgcc_data, 0o444, {'source': str(libgcc_source), 'package': abi_proof['package'], 'reason': 'Observed dynamic unwind mapping in attempt1'})
    for name, expected in KEY_HASHES.items():
        if name not in rows or sha(rows[name][0]) != expected:
            raise ValueError('Known ABI/source pin mismatch: ' + name)
    for name in ('worker.pl', 'cognitive_bridge.py', 'cognition_protocol.py', 'launch.py'):
        path = HERE / 'source' / name
        rows['capsule/bridge/' + name] = (path.read_bytes(), 0o444, {'source': str(path)})
    old_smoke = ROOT / 'boot/userland/petta_smoke.pl'
    smoke = replace_once(old_smoke.read_bytes(), b"           format('ROKO_GUEST_OMEGA_MESSAGES_PASSED counts=0,1,0~n')", b"           janus:py_call(cognitive_bridge:runtime_attestation(), @(true)),\n           format('ROKO_GUEST_OMEGA_MESSAGES_PASSED counts=0,1,0~n')")
    rows['capsule/bridge/primitive-smoke.pl'] = (smoke, 0o444, {'source': str(old_smoke), 'transform': 'append runtime map attestation to exact earlier fixture'})
    launcher = HERE / 'source/launch.py'
    smoke_launcher = replace_once(launcher.read_bytes(), b"'bridge/worker.pl'", b"'bridge/primitive-smoke.pl'")
    rows['capsule/bridge/launch-smoke.py'] = (smoke_launcher, 0o444, {'source': str(launcher), 'transform': 'fixed primitive smoke entry point'})
    for name in ('working_state.py', 'state_store.py', 'avatar_events.py'):
        path = ROOT / 'adapters' / name
        rows['roko/adapters/' + name] = (path.read_bytes(), 0o444, {'source': str(path)})
    for name in ('guest_cognition.py', 'cognition_protocol.py'):
        path = HERE / 'source' / name
        rows['roko/adapters/' + name] = (path.read_bytes(), 0o444, {'source': str(path)})
    cli = ROOT / 'scripts/roko.py'
    rows['roko/scripts/roko.py'] = (cli_variant(cli.read_bytes()), 0o444,
                                  {'source': str(cli), 'transform': 'cli_variant'})
    # The status command reads this lock, but no model is copied or attached.
    path = ROOT / 'granite-model.lock.json'
    rows['roko/granite-model.lock.json'] = (path.read_bytes(), 0o444, {'source': str(path)})
    return rows, {'boot/guest-userland-files.lock.json': sha(lock_bytes),
                  'runtime-build.lock.json': sha((ROOT / 'runtime-build.lock.json').read_bytes()),
                  'boot/tooling-files.lock.json': sha((ROOT / 'boot/tooling-files.lock.json').read_bytes()),
                  'libgcc-static-v3/validation.json': sha((ROOT / 'results/cognitive-capsule-preparation/libgcc-static-v3/validation.json').read_bytes())}


def inspect(rows, locks):
    total = sum(len(row[0]) for row in rows.values())
    if total > CAP:
        raise ValueError('Separate cognitive overlay exceeds128MiB')
    elf = {name: metadata for name, (data, mode, source) in rows.items()
           if (metadata := elf_metadata(data)) is not None}
    # Private explicit lookup order. No system overwrite and no name-only admission.
    prefixes = ('capsule/system/', 'capsule/python/lib/', 'capsule/swipl/lib/x86_64-linux/')
    resolution = {}
    for metadata in elf.values():
        for needed in metadata['needed']:
            candidates = [prefix + needed for prefix in prefixes if prefix + needed in rows]
            if len(candidates) != 1:
                raise ValueError('Missing or ambiguous locked loader dependency: ' + needed)
            resolution[needed] = candidates[0]
    if 'capsule/system/libgcc_s.so.1' not in rows:
        raise ValueError('Required runtime-observed dynamic libgcc dependency missing')
    resolution['libgcc_s.so.1'] = 'capsule/system/libgcc_s.so.1'
    if 'libpython3.12.so.1.0' not in elf['capsule/swipl/lib/x86_64-linux/janus.so']['needed']:
        raise ValueError('Janus no longer has the expected3.12 embed dependency')
    return {'version': 1, 'status': 'prepared-not-native-tested', 'payload_cap_bytes': CAP,
            'payload_bytes': total, 'pins': PINS, 'source_locks': locks,
            'files': {name: {'sha256': sha(data), 'bytes': len(data), 'mode': mode}
                      for name, (data, mode, source) in rows.items()},
            'sources': {name: source for name, (data, mode, source) in rows.items()},
            'elf_metadata': elf, 'private_resolution': resolution,
            'authority': 'No native execution, model, scheduler, actions or release permission',
            'limits': {'child_wall_seconds': 30, 'prolog_stack_mib': 64,
                       'child_sampled_rss_mib': 256, 'child_address_space_mib': 512,
                       'guest_available_floor_mib': 512, 'host_available_floor_mib': 2048,
                       'host_free_disk_floor_mib': 4096},
            'limitations': ['Static metadata closure only; relocation and actual loaded-library maps untested.',
                           'Trusted fixed fixture, not a hostile-code sandbox.',
                           'Inherited3.12 runtime provenance and redistribution clearance remain incomplete.']}


def prepare(freeze=False):
    rows, locks = inputs()
    result = inspect(rows, locks)
    if freeze:
        if shutil.disk_usage(ROOT).free < RESERVE + result['payload_bytes'] + 2 * 1024**2:
            raise ValueError('Cannot stage while preserving4GiB disk reserve')
        OUT.mkdir(parents=True, mode=0o700, exist_ok=False)
        for name, (data, mode, source) in rows.items():
            path = OUT / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            previous = PREVIOUS / name
            # Reuse only verified identical immutable bytes/mode. Never write or
            # chmod through a link to the previous frozen stage.
            if previous.is_file() and not previous.is_symlink() and stat.S_IMODE(previous.stat().st_mode) == mode and previous.read_bytes() == data:
                os.link(previous, path)
            else:
                path.write_bytes(data)
                path.chmod(mode)
        result['recipe_sha256'] = {str(p.relative_to(HERE)): sha(p.read_bytes())
                                   for p in [HERE / 'prepare.py', *sorted((HERE / 'source').glob('*'))]
                                   if p.is_file()}
        (OUT / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
        (OUT / 'manifest.json').chmod(0o444)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    report = prepare(args.freeze)
    print(json.dumps({key: report[key] for key in ('status', 'payload_bytes', 'pins', 'private_resolution')}, indent=2))
