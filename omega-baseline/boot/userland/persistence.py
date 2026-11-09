"""Explicit checkpoint snapshots on a dedicated raw virtio disk; no host mounts.

Two alternating slots retain the preceding committed snapshot after interrupted
writes. Checksums detect corruption, not malicious modification. Call only while
controller writers are stopped. This is not a general-purpose filesystem.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys

SLOT_BYTES = 16 * 1024 * 1024
DISK_BYTES = 2 * SLOT_BYTES
MAGIC = b'ROKO-STATE-v1\0\0\0'
HEADER = struct.Struct('<16sQQ32s')
MAX_FILES = 256


def digest(sequence, payload):
    return hashlib.sha256(struct.pack('<QQ', sequence, len(payload)) + payload).digest()


def latest(fd):
    records = []
    nonzero = False
    for index in range(2):
        raw = os.pread(fd, SLOT_BYTES, index * SLOT_BYTES)
        if len(raw) != SLOT_BYTES:
            raise ValueError('Dedicated disk has incorrect size')
        nonzero |= any(raw)
        magic, sequence, length, checksum = HEADER.unpack(raw[:HEADER.size])
        if magic != MAGIC or not 0 < length <= SLOT_BYTES - HEADER.size or not sequence:
            continue
        payload = raw[HEADER.size:HEADER.size + length]
        if digest(sequence, payload) == checksum:
            records.append((sequence, index, payload))
    if not records:
        if nonzero:
            raise ValueError('No valid snapshot: refusing unknown or corrupt disk')
        return None
    if len(records) == 2 and records[0][0] == records[1][0]:
        raise ValueError('Ambiguous snapshot sequence')
    return max(records)


def write_all(fd, data, offset):
    while data:
        count = os.pwrite(fd, data, offset)
        if count <= 0:
            raise OSError('Short disk write')
        offset += count
        data = data[count:]


def commit(fd, payload):
    if not 0 < len(payload) <= SLOT_BYTES - HEADER.size:
        raise ValueError('Snapshot exceeds disk slot')
    old = latest(fd)
    sequence, index = (old[0] + 1, 1 - old[1]) if old else (1, 0)
    offset = index * SLOT_BYTES
    write_all(fd, b'\0' * HEADER.size, offset)
    os.fsync(fd)
    write_all(fd, payload, offset + HEADER.size)
    os.fsync(fd)
    write_all(fd, HEADER.pack(MAGIC, sequence, len(payload), digest(sequence, payload)), offset)
    os.fsync(fd)
    return sequence


def validate(payload):
    from state_store import canonical, restore, unique, MAX_BYTES
    data = json.loads(payload, object_pairs_hook=unique)
    if type(data) is not dict or set(data) != {'schema', 'files'} or type(data['schema']) is not int or data['schema'] != 1:
        raise ValueError('Invalid snapshot schema')
    files = data['files']
    if type(files) is not dict or len(files) > MAX_FILES:
        raise ValueError('Invalid snapshot files')
    for name, envelope in files.items():
        if type(envelope) is not dict or set(envelope) != {'version','revision','payload','sha256'}:
            raise ValueError('Invalid checkpoint envelope')
        if type(envelope['version']) is not int or envelope['version'] != 1 or type(envelope['revision']) is not int or envelope['revision'] < 1:
            raise ValueError('Invalid checkpoint revision')
        state = restore(envelope['payload'])
        if name != hashlib.sha256(state.task_id.encode()).hexdigest() + '.json':
            raise ValueError('Invalid checkpoint filename')
        body = {k:envelope[k] for k in ('version','revision','payload')}
        if hashlib.sha256(canonical(body)).hexdigest() != envelope['sha256'] or len(canonical(envelope)) > MAX_BYTES:
            raise ValueError('Invalid checkpoint checksum or size')
    return files


def export(directory):
    from state_store import StateStore, canonical
    store = StateStore(directory)
    files = {}
    for path in sorted(directory.glob('*.json')):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Checkpoint must be regular')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(1024 * 1024 + 1)
        finally:
            os.close(fd)
        envelope = json.loads(raw)
        store.load(envelope['payload']['task_id'])
        files[path.name] = envelope
    payload = canonical({'schema':1, 'files':files})
    validate(payload)
    return payload


def restore_files(directory, payload):
    from state_store import canonical
    files = validate(payload)
    if any(directory.iterdir()):
        raise ValueError('Restore requires an empty state directory')
    for name, value in files.items():
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['save', 'load'])
    args = parser.parse_args()
    # Runtime entrypoint refuses host use and arbitrary device/path arguments.
    if not Path('/etc/roko-profile.json').is_file() or Path('/proc/1/comm').read_text().strip() != 'init':
        raise SystemExit('Roko guest only')
    sys.path.insert(0, '/opt/roko/adapters')
    fd = os.open('/dev/vda', os.O_RDWR | os.O_NOFOLLOW)
    try:
        if not stat.S_ISBLK(os.fstat(fd).st_mode):
            raise ValueError('Expected dedicated guest block device')
        if os.lseek(fd, 0, os.SEEK_END) != DISK_BYTES:
            raise ValueError('Expected dedicated 32 MiB guest disk')
        directory = Path('/var/lib/roko')
        if args.operation == 'save':
            sequence = commit(fd, export(directory))
        else:
            record = latest(fd)
            if record is None:
                raise ValueError('Disk has no saved snapshot')
            sequence, _, payload = record
            restore_files(directory, payload)
        print('ROKO_PERSISTENCE_' + args.operation.upper() + '_PASSED sequence=' + str(sequence), flush=True)
    finally:
        os.close(fd)

if __name__ == '__main__':
    main()
