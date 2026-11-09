#!/usr/bin/env python3
"""Authenticate an offline release without extracting, installing or booting it.

Trust anchors and rollback floor must come from trusted provisioning/storage,
never from the downloaded bundle. This is admission only, not an updater.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

from release import canonical, unique_object

DOMAIN = b'ROKO-OFFLINE-RELEASE-V1\n'
MAX_BUNDLE = 256 * 1024**3


def read_regular(path, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise ValueError('Expected bounded singly-linked regular input')
        raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError('Input grew past bound')
        return raw


def envelope(raw):
    value = json.loads(raw, object_pairs_hook=unique_object)
    if type(value) is not dict or set(value) != {'schema', 'release', 'sequence', 'bytes', 'sha256'}:
        raise ValueError('Invalid signed release envelope')
    if value['schema'] != 'roko-signed-release-v1':
        raise ValueError('Unsupported signed release schema')
    if type(value['release']) is not str or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}', value['release']):
        raise ValueError('Invalid release identity')
    if type(value['sequence']) is not int or not 1 <= value['sequence'] < 2**63:
        raise ValueError('Invalid release sequence')
    if type(value['bytes']) is not int or not 0 < value['bytes'] <= MAX_BUNDLE:
        raise ValueError('Invalid release size')
    if type(value['sha256']) is not str or not re.fullmatch(r'[0-9a-f]{64}', value['sha256']):
        raise ValueError('Invalid release digest')
    if raw != canonical(value):
        raise ValueError('Signed envelope must use canonical serialization')
    return value


def verify(bundle, metadata, signature, public_key, minimum_sequence, *, openssl='/usr/bin/openssl'):
    if type(minimum_sequence) is not int or not 1 <= minimum_sequence < 2**63:
        raise ValueError('Explicit trusted rollback floor required')
    raw = read_regular(metadata, 4096)
    value = envelope(raw)
    if value['sequence'] < minimum_sequence:
        raise ValueError('Release is below the trusted rollback floor')
    sig = read_regular(signature, 64)
    if len(sig) != 64:
        raise ValueError('Expected Ed25519 signature')
    key = read_regular(public_key, 4096)
    # Require an Ed25519 SubjectPublicKeyInfo, not an algorithm selected by metadata.
    with tempfile.TemporaryDirectory(prefix='roko-verify-') as temp:
        root = Path(temp)
        (root/'key.pem').write_bytes(key)
        parsed = subprocess.run([openssl, 'pkey', '-pubin', '-in', str(root/'key.pem'), '-outform', 'DER'],
                                capture_output=True, timeout=10, check=True)
        der = parsed.stdout
        if len(der) != 44 or not der.startswith(bytes.fromhex('302a300506032b6570032100')):
            raise ValueError('Trust anchor must be an Ed25519 public key')
        (root/'message').write_bytes(DOMAIN + raw)
        (root/'signature').write_bytes(sig)
        result = subprocess.run([openssl, 'pkeyutl', '-verify', '-pubin', '-inkey', str(root/'key.pem'),
                                 '-rawin', '-in', str(root/'message'), '-sigfile', str(root/'signature')],
                                capture_output=True, timeout=10)
        if result.returncode:
            raise ValueError('Release signature verification failed')
    fd = os.open(bundle, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != value['bytes']:
            raise ValueError('Release file type/link count/size mismatch')
        digest = hashlib.sha256()
        remaining = value['bytes']
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError('Truncated release')
            remaining -= len(block)
            digest.update(block)
        after = os.fstat(stream.fileno())
        identity = lambda info: (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
        if stream.read(1) or identity(before) != identity(after):
            raise ValueError('Release changed during verification')
        if digest.hexdigest() != value['sha256']:
            raise ValueError('Signed release digest mismatch')
    return {**value, 'signature_verified': True, 'key_sha256': hashlib.sha256(der).hexdigest(),
            'minimum_sequence': minimum_sequence, 'installed': False, 'boot_selected': False,
            'rollback_floor_updated': False,
            'scope': 'Observed bytes only; reverify or retain a protected descriptor before use'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'metadata', 'signature', 'public_key'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--minimum-sequence', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.bundle, args.metadata, args.signature, args.public_key,
                            args.minimum_sequence), indent=2, sort_keys=True))
