"""Narrow future synthetic-only QEMU attachment. Import does not open/attach."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

from synthetic import specification


def identity(info):
    return {'dev': info.st_dev, 'ino': info.st_ino, 'bytes': info.st_size,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
            'owner': info.st_uid, 'mode': stat.S_IMODE(info.st_mode), 'links': info.st_nlink}


def verify(fd, previous=None):
    info = os.fstat(fd)
    spec = specification()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o444 or info.st_size != spec['source_bytes']
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise ValueError('Expected exact inert read-only owned regular fixture')
    before = identity(info)
    digest = hashlib.sha256(os.pread(fd, info.st_size, 0)).hexdigest()
    if digest != spec['sha256'] or before != identity(os.fstat(fd)):
        raise ValueError('Synthetic fixture changed or hash mismatch')
    record = dict(before, sha256=digest, access='O_RDONLY')
    if previous is not None and record != previous:
        raise ValueError('Synthetic fixture identity changed after use')
    return record


def open_fixture(directory):
    directory = Path(directory)
    if not directory.is_absolute() or directory != directory.resolve():
        raise ValueError('Fixture directory must be canonical')
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Fixture directory must be private and owned')
        fd = os.open('synthetic.raw', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        return fd, verify(fd)
    except BaseException:
        os.close(fd)
        raise


def attachment(fd):
    verify(fd)
    return ['-blockdev', json.dumps({'driver': 'file', 'filename': f'/proc/self/fd/{fd}',
                                    'node-name': 'rawsyntheticfile', 'read-only': True,
                                    'cache': {'direct': False, 'no-flush': False}}),
            '-blockdev', json.dumps({'driver': 'raw', 'file': 'rawsyntheticfile',
                                    'node-name': 'rawsyntheticdata', 'read-only': True}),
            '-device', 'virtio-blk-pci,drive=rawsyntheticdata,serial=roko-raw-synthetic']
