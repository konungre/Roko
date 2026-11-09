"""Admit only the exact existing pinned Granite regular inode, read-only.

Import and metadata inspection do not hash, open, attach or copy model bytes.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = 'models/hub/models--ibm-granite--granite-4.0-h-tiny-GGUF/snapshots/08d5a8a9741dd5c1a95d2d39e25253226aa1464e/granite-4.0-h-tiny-Q4_K_M.gguf'
DATA_PATH = 'models/hub/blobs/4e/4e639bc6f768c6ef6853ec9936ab018a24f2edc76739466220d4bd783ca257d8'
SHA = '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
SIZE = 4230976352


def metadata(info):
    return {'dev': info.st_dev, 'ino': info.st_ino, 'bytes': info.st_size,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
            'owner': info.st_uid, 'mode': stat.S_IMODE(info.st_mode), 'links': info.st_nlink}


def verify(fd, previous=None, seconds=120):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o444 or info.st_size != SIZE
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise ValueError('Expected exact locked owned regular O_RDONLY model')
    before = metadata(info)
    digest = hashlib.sha256()
    offset = 0
    deadline = time.monotonic() + seconds
    while offset < SIZE:
        if time.monotonic() >= deadline:
            raise TimeoutError('Host model hash deadline')
        data = os.pread(fd, min(4 * 1024**2, SIZE-offset), offset)
        if not data:
            raise ValueError('Short model read')
        digest.update(data)
        offset += len(data)
    if digest.hexdigest() != SHA or before != metadata(os.fstat(fd)):
        raise ValueError('Locked model hash or metadata changed')
    result = dict(before, sha256=digest.hexdigest(), access='O_RDONLY')
    if previous is not None and result != previous:
        raise ValueError('Model identity changed after VM use')
    return result


def open_model():
    lock = json.loads((ROOT / 'granite-model.lock.json').read_text())
    if (lock['path'] != LOCK_PATH or lock['bytes'] != SIZE or lock['sha256'] != SHA
            or lock['revision'] != '08d5a8a9741dd5c1a95d2d39e25253226aa1464e'):
        raise ValueError('Unexpected locked model source')
    target = ROOT / DATA_PATH
    if (ROOT / LOCK_PATH).resolve(strict=True) != target:
        raise ValueError('Cache symlinks no longer resolve to the approved data inode path')
    # Pin and verify every canonical workspace-relative directory; only the final
    # model fd is inherited by QEMU, never a host directory descriptor.
    current = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in Path(DATA_PATH).parts[:-1]:
            info = os.fstat(current)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError('Unowned or writable model ancestor')
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        info = os.fstat(current)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError('Unowned or writable model directory')
        fd = os.open(target.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
    finally:
        os.close(current)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return fd, verify(fd)
    except BaseException:
        os.close(fd)
        raise


def attachment(fd, admitted):
    # Full digest was checked through this same live fd. No path is reopened.
    if (metadata(os.fstat(fd)) != {k: admitted[k] for k in metadata(os.fstat(fd))}
            or admitted['sha256'] != SHA or admitted['access'] != 'O_RDONLY'
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise ValueError('Model descriptor changed since admission')
    return ['-blockdev', json.dumps({'driver':'file','filename':f'/proc/self/fd/{fd}',
                                    'node-name':'granitemodelfile','read-only':True,
                                    'cache':{'direct':False,'no-flush':False}}),
            '-blockdev', json.dumps({'driver':'raw','file':'granitemodelfile',
                                    'node-name':'granitemodeldata','read-only':True}),
            '-device','virtio-blk-pci,drive=granitemodeldata,serial=roko-granite-model']
