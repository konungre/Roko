#!/usr/bin/env python3
"""Stage authenticated bytes in a new private directory; never select a boot slot.

An interrupted directory is preserved for inspection, never adopted or overwritten.
READY is a hint only: recovery must authenticate the staged bytes again.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat

from release import canonical
from verify_release import verify


def private_parent(path):
    if path != path.resolve():
        raise ValueError('Canonical staging parent required')
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Owned private staging parent required')


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_bounded(source, target, maximum):
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as incoming:
        info = os.fstat(incoming.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise ValueError('Invalid staging input')
        with target.open('xb') as outgoing:
            os.chmod(target, 0o600)
            remaining = maximum
            while remaining:
                block = incoming.read(min(1024 * 1024, remaining))
                if not block:
                    break
                outgoing.write(block)
                remaining -= len(block)
            if incoming.read(1):
                raise ValueError('Staging input grew beyond signed bound')
            outgoing.flush()
            os.fsync(outgoing.fileno())


def stage(bundle, metadata, signature, public_key, minimum_sequence, output, *, checkpoint=lambda phase: None):
    if os.geteuid() == 0:
        raise ValueError('Staging must run as an unprivileged user')
    output = Path(output)
    private_parent(output.parent)
    # Refuse invalid signatures/rollback before allocating the payload copy.
    admitted = verify(bundle, metadata, signature, public_key, minimum_sequence)
    if shutil.disk_usage(output.parent).free < admitted['bytes'] + 64 * 1024**2:
        raise ValueError('Insufficient space including staging reserve')
    output.mkdir(mode=0o700)  # exclusive job ownership; never reuse interrupted output
    sync_directory(output.parent)
    checkpoint('directory-durable')
    copy_bounded(metadata, output/'release.json', 4096)
    copy_bounded(signature, output/'release.sig', 64)
    checkpoint('metadata-durable')
    copy_bounded(bundle, output/'bundle.partial', admitted['bytes'])
    checkpoint('payload-durable')
    # Authenticate the actual copy, including metadata; source mutation cannot
    # substitute a different admitted release between the two checks.
    copied = verify(output/'bundle.partial', output/'release.json', output/'release.sig', public_key, minimum_sequence)
    for field in ('release', 'sequence', 'bytes', 'sha256', 'key_sha256'):
        if copied[field] != admitted[field]:
            raise ValueError('Source identity changed during staging')
    checkpoint('copy-authenticated')
    os.rename(output/'bundle.partial', output/'bundle.tar')
    sync_directory(output)
    checkpoint('payload-published')
    receipt = {**copied, 'schema': 'roko-staged-release-v1', 'installed': False,
               'boot_selected': False, 'rollback_floor_updated': False}
    with (output/'READY.partial').open('xb') as stream:
        stream.write(canonical(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    checkpoint('receipt-durable')
    os.rename(output/'READY.partial', output/'READY')
    sync_directory(output)
    checkpoint('ready-durable')
    return receipt


def inspect(output, public_key, minimum_sequence):
    output = Path(output)
    private_parent(output)
    if not (output/'READY').exists():
        return {'state': 'incomplete', 'installed': False, 'boot_selected': False}
    # Never trust READY or a previous receipt as an authorization token.
    result = verify(output/'bundle.tar', output/'release.json', output/'release.sig', public_key, minimum_sequence)
    return {**result, 'state': 'authenticated-staging', 'installed': False, 'boot_selected': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'metadata', 'signature', 'public_key', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--minimum-sequence', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.bundle, args.metadata, args.signature, args.public_key,
                           args.minimum_sequence, args.output), indent=2, sort_keys=True))
