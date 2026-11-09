#!/usr/bin/env python3
"""Pure source plan and explicitly reviewed initramfs packaging. Never boots/mounts."""
import argparse
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]
REPO = WORK / 'omega-baseline'
TOOLS = WORK / 'recovery-second/runtime/vm-tooling'
KERNEL_RELEASE = '6.12.115+deb13.1-amd64'
MODULES = TOOLS / 'usr/lib/modules' / KERNEL_RELEASE
TOOL_LOCK = WORK / 'recovery-second/runtime/vm-staged-files.lock.json'
PET_LOCK = WORK / 'roko-showcase-stage-v4.lock.json'
PET_SHA = '77d8916d3752751431b63523b4d9785bccc8a945ec3cdc746818635b486fd5d3'
LIVE_MAP = REPO / 'desktop/live-request-media/staging-map.json'
LIVE_SHA = '9df964ca0f344582a19b85c4fb7cada1dc5a6dec3381183aeab62d73d6d43743'
FW = WORK / 'recovery-showcase/liveboot/firmware'
FW_SHA = 'df603d5626b511d010e166a65e74faf15eaf7ba3947680d3c40f5e04bbc56c27'
ROOT_SHA = 'b7770c5352b5a38cbe5f9825133e381ba5e2772874d81e991ce04c1c2152e933'
MODEL_SHA = '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
CAP = 160 * 1024**2
EARLY = ['crc32c_generic', 'loop', 'overlay', 'ext4', 'isofs', 'sd_mod', 'sr_mod', 'ahci',
         'usb_storage', 'uas', 'xhci_pci', 'ehci_pci', 'ohci_pci', 'uhci_hcd', 'virtio_blk']
LATE = ['virtio_gpu', 'virtio_input', 'evdev', 'hid_generic', 'usbhid', 'psmouse', 'i915', 'xe']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def read(path, expected=None, cap=64 * 1024**2):
    path = Path(path)
    require(not path.is_symlink(), 'Source is symlink: ' + str(path))
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'Source size/type: ' + str(path))
        data = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns), 'Source changed: ' + str(path))
    require(expected is None or sha(data) == expected, 'Source hash: ' + str(path))
    return data


def relative(path):
    p = PurePosixPath(path)
    require(not p.is_absolute() and str(p) == path and '..' not in p.parts and path not in ('', '.'), 'Unsafe archive path')
    return path


def module_info(data):
    def values(key):
        return [x.decode('ascii') for x in re.findall(b'\x00' + key.encode() + b'=([^\x00]*)', data)]
    deps = values('depends')
    require(len(deps) <= 1, 'Ambiguous module dependency metadata')
    return {'depends': [x.replace('-', '_') for x in (deps[0].split(',') if deps and deps[0] else [])],
            'firmware': values('firmware'), 'vermagic': values('vermagic'), 'softdep': values('softdep')}


def module_closure(roots, index, builtin, get_info):
    order, visiting, done = [], set(), set()
    def visit(name):
        if name in builtin or name in done:
            return
        require(name not in visiting, 'Kernel module dependency cycle')
        require(name in index, 'Missing kernel module: ' + name)
        visiting.add(name)
        for dependency in get_info(name)['depends']:
            visit(dependency)
        visiting.remove(name)
        done.add(name)
        order.append(name)
    for name in roots:
        visit(name)
    return order


def media_manifest():
    return {'schema': 'roko-live-media-v1', 'label': 'ROKO_SHOWCASE',
            'root': {'path': '/roko/root.ext4', 'bytes': 3221225472, 'sha256': ROOT_SHA},
            'model': {'path': '/roko/model/granite-4.0-h-tiny-Q4_K_M.gguf', 'bytes': 4230976352, 'sha256': MODEL_SHA},
            'persistent_state': False, 'installation': False}


def plan():
    lock = json.loads(read(TOOL_LOCK))['files']
    read(TOOLS / 'boot' / ('vmlinuz-' + KERNEL_RELEASE), lock['boot/vmlinuz-' + KERNEL_RELEASE]['sha256'])
    pet = json.loads(read(PET_LOCK, PET_SHA))
    live = json.loads(read(LIVE_MAP, LIVE_SHA))
    firmware = json.loads(read(FW / 'firmware-manifest.json', FW_SHA))
    rows = {}
    def file(src, dest, mode=0o444, expected=None, transform=None):
        relative(dest)
        data = read(src, expected)
        if transform == 'xz':
            data = lzma.decompress(data)
        require(dest not in rows, 'Duplicate archive destination: ' + dest)
        rows[dest] = {'kind': 'file', 'source': str(Path(src).relative_to(WORK)), 'source_sha256': sha(read(src)),
                      'sha256': sha(data), 'bytes': len(data), 'mode': mode, 'transform': transform}
    def generated(dest, data, mode=0o444):
        relative(dest)
        require(dest not in rows, 'Duplicate generated path')
        rows[dest] = {'kind': 'generated', 'text': data, 'sha256': sha(data.encode()), 'bytes': len(data.encode()), 'mode': mode}
    busybox = TOOLS / 'usr/bin/busybox'
    bb_data = read(busybox, lock['usr/bin/busybox']['sha256'])
    require(bb_data[:5] == b'\x7fELF\x02' and bb_data[5] == 1, 'Expected ELF64 little-endian BusyBox')
    phoff = struct.unpack_from('<Q', bb_data, 32)[0]
    phsize, phcount = struct.unpack_from('<HH', bb_data, 54)
    require(phsize >= 56 and phoff + phsize * phcount <= len(bb_data), 'Invalid BusyBox ELF headers')
    require(all(struct.unpack_from('<I', bb_data, phoff + i * phsize)[0] != 3 for i in range(phcount)), 'Bootstrap BusyBox is not static')
    for applet in ['cat', 'uname', 'dd', 'od', 'tr', 'sed', 'losetup', 'sha256sum', 'switch_root', 'poweroff', 'insmod', 'mount', 'stat', 'cut', 'cp', 'rm', 'mkdir', 'chmod', 'sleep', 'id', 'kill']:
        require(b'\0' + applet.encode() + b'\0' in bb_data, 'Missing BusyBox applet: ' + applet)
    file(busybox, 'bin/busybox', 0o755, lock['usr/bin/busybox']['sha256'])
    file(HERE / 'init.sh', 'init', 0o755)
    generated('etc/kernel-release', KERNEL_RELEASE + '\n')
    generated('etc/media-manifest.sha256', sha(encoded(media_manifest())) + '\n')
    index = {p.name.removesuffix('.ko.xz').replace('-', '_'): p for p in MODULES.rglob('*.ko.xz')}
    builtin = {Path(p).name.removesuffix('.ko').replace('-', '_') for p in (MODULES / 'modules.builtin').read_text().splitlines()}
    metadata = {}
    def info(name):
        if name not in metadata:
            path = index[name]
            record = lock[str(path.relative_to(TOOLS))]
            data = read(path, record['sha256'])
            raw = lzma.decompress(data)
            entry = module_info(raw)
            require(entry['vermagic'] and entry['vermagic'][0].startswith(KERNEL_RELEASE + ' '), 'Kernel module version mismatch')
            metadata[name] = dict(entry, source=str(path.relative_to(WORK)), source_sha256=sha(data), sha256=sha(raw), bytes=len(raw))
        return metadata[name]
    early = module_closure(EARLY, index, builtin, info)
    late = [name for name in module_closure(LATE, index, builtin, info) if name not in early]
    for name in early + late:
        file(index[name], 'modules/' + name + '.ko', expected=metadata[name]['source_sha256'], transform='xz')
    generated('etc/early-module-order', '\n'.join(early) + '\n')
    generated('payload/root/etc/roko-showcase/late-module-order', '\n'.join(late) + '\n')
    for dest, expected in pet.items():
        # Explicit derivative launcher pins Python 3.13 and the new media CLI;
        # all other avatar source/artwork bytes remain unchanged.
        if dest == 'usr/bin/roko-companion':
            file(HERE / 'roko-companion-media.sh', 'payload/root/' + dest, 0o755)
        else:
            file(WORK / 'roko-showcase-stage-v4' / dest, 'payload/root/' + dest,
                 0o755 if dest.endswith('roko-window-tracker') else 0o444, expected)
    for row in live['entries']:
        target = row['destination']
        require(target.startswith(('/run/roko-guest-cognition/', '/opt/roko/desktop/live-request/')), 'Unexpected live target')
        dest = 'payload/run/' + target[5:] if target.startswith('/run/') else 'payload/root/' + target.lstrip('/')
        file(Path(row['source']), dest, row['mode'], row['sha256'])
    for name, dest, mode in [('session.sh', 'usr/libexec/roko-showcase-session', 0o755),
                             ('supervisor.py', 'usr/libexec/roko-showcase-supervisor.py', 0o444),
                             ('poweroff.sh', 'usr/bin/roko-showcase-poweroff', 0o755),
                             ('roko-showcase-poweroff.desktop', 'usr/share/applications/roko-showcase-poweroff.desktop', 0o444),
                             ('background.ron', 'etc/roko-showcase/background.ron', 0o444),
                             ('background.ron', 'usr/share/cosmic/com.system76.CosmicBackground/v1/all', 0o444)]:
        file(HERE / name, 'payload/root/' + dest, mode)
    # Root's /lib is not a usrmerge link. Place firmware in kernel's search path.
    fw_paths = {}
    for dest, record in firmware['files'].items():
        target = dest.replace('usr/lib/firmware/', 'lib/firmware/', 1)
        file(FW / 'runtime-root' / dest, 'payload/root/' + target, 0o444, record['sha256'])
        fw_paths[dest] = record['sha256']
    for dest, record in firmware['symlinks'].items():
        path = FW / 'runtime-root' / dest
        resolved = path.resolve(strict=True)
        resolved.relative_to((FW / 'runtime-root/usr/lib/firmware').resolve())
        require(str(resolved.relative_to(FW / 'runtime-root')) in fw_paths, 'Firmware link outside pinned files')
        target = dest.replace('usr/lib/firmware/', 'lib/firmware/', 1)
        file(resolved, 'payload/root/' + target, 0o444, fw_paths[str(resolved.relative_to(FW / 'runtime-root'))])
    readback = json.loads(read(REPO / 'recovery/guest-overlays/ext4-harness/root-attempt-001/readback.json'))
    runtime = json.loads(read(REPO / 'recovery/guest-cognition/model-runtime-plan/component-002/granite-portable-runtime.lock.json'))
    matches = {p: readback['payload_sha256'].get(p.lstrip('/')) == h for p, h in runtime['system_files'].items()}
    require(all(matches.values()), 'Root system runtime mismatch')
    size = sum(row['bytes'] for row in rows.values())
    require(size + len(rows) * 512 < CAP, 'Initramfs source payload cap')
    available_fw = {p.removeprefix('usr/lib/firmware/') for p in list(firmware['files']) + list(firmware['symlinks']) if p.startswith('usr/lib/firmware/')}
    missing_fw = sorted({fw for info in metadata.values() for fw in info['firmware'] if fw not in available_fw})
    return {'schema': 'roko-live-bootstrap-source-v1', 'source_only': True, 'boot_tested': False,
            'native_executed': False, 'root_image_created': False, 'source_plan_creates_no_root_or_model_copy': True,
            'source_tools': {name: sha(read(HERE / name)) for name in ['source.py', 'test_source.py', 'PLAN.md', 'evidence/schema-provenance.json']},
            'kernel': {'source': str((TOOLS / 'boot' / ('vmlinuz-' + KERNEL_RELEASE)).relative_to(WORK)),
                       'sha256': lock['boot/vmlinuz-' + KERNEL_RELEASE]['sha256']},
            'input_locks': {'basilisk': PET_SHA, 'live_endpoint': LIVE_SHA, 'intel_firmware': FW_SHA, 'debian_tools': sha(read(TOOL_LOCK))},
            'media_manifest': media_manifest(), 'media_manifest_sha256': sha(encoded(media_manifest())),
            'entries': rows, 'module_metadata': metadata, 'early_modules': early, 'late_modules': late,
            'firmware_names_unavailable': missing_fw, 'system_runtime_readback_matches': matches,
            'source_payload_bytes': size, 'initramfs_uncompressed_cap': CAP,
            'explicit_soft_dependencies': {'ext4': ['crc32c_generic'], 'jbd2': ['crc32c_generic'], 'ohci_pci': ['ehci_pci'], 'uhci_hcd': ['ehci_pci']},
            'limits': ['No persistent state or installation', 'Unknown Intel hardware untested',
                       'No Secure Boot support claimed', 'No model or desktop runtime tested',
                       'No model inference until explicit basilisk request', 'Reduced root COSMIC subset, root user, no logind/lockscreen']}


def entry(name, data, mode, ino, major=0, minor=0):
    rawname = name.encode() + b'\0'
    fields = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(rawname), 0]
    header = b'070701' + ''.join(f'{v:08x}' for v in fields).encode()
    out = header + rawname
    out += b'\0' * (-len(out) % 4)
    return out + data + b'\0' * (-len(data) % 4)


def inspect_archive(path, expected):
    """Independent streaming newc readback; never extracts or executes."""
    found = {}
    with gzip.open(path, 'rb') as stream:
        while True:
            header = stream.read(110)
            require(len(header) == 110 and header[:6] == b'070701', 'Bad newc header')
            values = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
            mode, size, namesize = values[1], values[6], values[11]
            require(0 < namesize <= 4096 and size <= CAP, 'Bad newc bounds')
            rawname = stream.read(namesize)
            require(len(rawname) == namesize and rawname[-1:] == b'\0', 'Bad newc name')
            name = rawname[:-1].decode()
            stream.read(-(110 + namesize) % 4)
            if name == 'TRAILER!!!':
                require(size == 0, 'Bad newc trailer')
                break
            relative(name)
            require(name not in found, 'Duplicate newc member')
            digest = hashlib.sha256()
            remaining = size
            while remaining:
                block = stream.read(min(1024**2, remaining))
                require(bool(block), 'Truncated newc data')
                digest.update(block)
                remaining -= len(block)
            stream.read(-size % 4)
            found[name] = {'bytes': size, 'mode': mode, 'sha256': digest.hexdigest()}
        require(not stream.read(1), 'Unexpected newc tail')
    require(found == expected, 'Independent archive readback mismatch')
    return len(found)


def assemble(document, expected, output):
    # An explicit CLI flag is identity binding, not a substitute for actual
    # source/runtime authorization. Caller must obtain the parent review first.
    require(sha(encoded(document)) == expected, 'Exact reviewed plan digest required')
    require(document == plan(), 'Source inputs changed after review')
    require(not output.exists() and not output.is_symlink(), 'Fresh output directory required')
    output.mkdir(mode=0o700, parents=False)
    rows = dict(document['entries'])
    directories = {'bin', 'dev', 'proc', 'sys', 'run', 'newroot', 'payload/root', 'payload/run'}
    for name in rows:
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != '.')
    members = {d: (b'', stat.S_IFDIR | 0o755, 0, 0) for d in directories}
    members['bin/sh'] = (b'busybox', stat.S_IFLNK | 0o777, 0, 0)
    members['dev/console'] = (b'', stat.S_IFCHR | 0o600, 5, 1)
    target = output / 'showcase.cpio.gz'
    actual = {}
    with target.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=1) as stream:
            length = 0
            for i, name in enumerate(sorted(set(members) | set(rows)), 1):
                if name in rows:
                    row = rows[name]
                    data = row['text'].encode() if row['kind'] == 'generated' else read(WORK / row['source'], row['source_sha256'])
                    if row.get('transform') == 'xz':
                        data = lzma.decompress(data)
                    require(sha(data) == row['sha256'] and len(data) == row['bytes'], 'Payload changed')
                    mode, major, minor = stat.S_IFREG | row['mode'], 0, 0
                else:
                    data, mode, major, minor = members[name]
                item = entry(name, data, mode, i, major, minor)
                stream.write(item)
                length += len(item)
                require(length <= CAP, 'Archive cap')
                actual[name] = {'bytes': len(data), 'mode': mode, 'sha256': sha(data)}
            stream.write(entry('TRAILER!!!', b'', 0, len(actual) + 1))
    inspect_archive(target, actual)
    (output / 'media-manifest.json').write_bytes(encoded(media_manifest()))
    result = {'schema': 'roko-live-bootstrap-build-v1', 'source_plan_sha256': expected,
              'archive': str(target.relative_to(WORK)), 'archive_sha256': sha(read(target, cap=CAP)),
              'archive_bytes': target.stat().st_size, 'entries': actual, 'independent_archive_readback': True, 'boot_tested': False, 'native_executed': False}
    (output / 'build-receipt.json').write_bytes(encoded(result))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['plan', 'assemble'])
    p.add_argument('--output', type=Path)
    p.add_argument('--reviewed-plan-sha256')
    args = p.parse_args()
    document = plan()
    if args.operation == 'plan':
        require(args.reviewed_plan_sha256 is None, 'Review digest is only for assembly')
        if args.output:
            require(not args.output.exists(), 'Do not overwrite a source checkpoint')
            args.output.write_bytes(encoded(document))
        print(json.dumps({'plan_sha256': sha(encoded(document)), 'entries': len(document['entries']),
                          'payload_bytes': document['source_payload_bytes'],
                          'missing_firmware_names': document['firmware_names_unavailable'], 'source_only': True}, indent=2))
    else:
        require(args.output and args.reviewed_plan_sha256, 'Explicit fresh output and reviewed plan hash required')
        print(json.dumps(assemble(document, args.reviewed_plan_sha256, args.output), indent=2))


if __name__ == '__main__':
    main()
