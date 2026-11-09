"""Fixed read-only regular model on live boot media, no arbitrary path API.

The bootstrap owns media discovery/label admission. This transport independently
requires its exact read-only mount and a read-only descriptor, hashes the exact
locked file, and retains that descriptor through native inference and posthash.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

MOUNT = Path('/run/roko-live-media')
MODEL = MOUNT / 'roko/model/granite-4.0-h-tiny-Q4_K_M.gguf'
MODEL_BYTES = 4230976352
MODEL_SHA = '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
TRANSPORT = 'readonly-regular-live-media-v1'
MOUNTINFO_CAP = 1024 * 1024


def _identity(info):
    return {'dev': info.st_dev, 'ino': info.st_ino, 'size': info.st_size,
            'mode': info.st_mode, 'links': info.st_nlink,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns}


def _unescape(value):
    # Kernel mountinfo escaping only. No generic backslash decoding or paths
    # derived from user/model content.
    return re.sub(r'\\(040|011|012|134)', lambda m: chr(int(m[1], 8)), value)


def mount_record(raw):
    """Pure parser. Reject hidden nested mounts, duplicate paths and writable media."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MOUNTINFO_CAP:
        raise ValueError('Mountinfo byte bound')
    text = raw.decode('utf-8', errors='strict')
    rows = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10 or fields.count('-') != 1:
            raise ValueError('Malformed mountinfo')
        separator = fields.index('-')
        if separator < 6 or len(fields) != separator + 4:
            raise ValueError('Malformed mountinfo fields')
        point = _unescape(fields[4])
        if point == str(MOUNT):
            if 'ro' not in fields[5].split(',') or 'rw' in fields[5].split(','):
                raise ValueError('Live medium mount is writable')
            if 'ro' not in fields[separator + 3].split(',') or 'rw' in fields[separator + 3].split(','):
                raise ValueError('Live medium filesystem is writable')
            if fields[separator + 1] not in ('iso9660', 'squashfs', 'vfat', 'ext4'):
                raise ValueError('Unadmitted live-media filesystem')
            rows.append({'mount_id': fields[0], 'parent_id': fields[1],
                'major_minor': fields[2], 'root': _unescape(fields[3]),
                'mountpoint': point, 'mount_options': fields[5],
                'filesystem': fields[separator + 1],
                'source': _unescape(fields[separator + 2]),
                'super_options': fields[separator + 3]})
        elif str(MODEL) == point or str(MODEL).startswith(point.rstrip('/') + '/') and point.startswith(str(MOUNT) + '/'):
            raise ValueError('Nested mount hides the model path')
    if len(rows) != 1:
        raise ValueError('Exactly one fixed live-media mount is required')
    return rows[0]


def current_mount():
    with Path('/proc/self/mountinfo').open('rb') as stream:
        return mount_record(stream.read(MOUNTINFO_CAP + 1))


def _open_fixed_model():
    """Walk from / using no-follow directory descriptors, never a mutable alias."""
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in MODEL.parts[1:-1]:
            next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            os.close(directory)
            directory = next_fd
        return os.open(MODEL.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def _metadata(fd, mount):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size != MODEL_BYTES or info.st_nlink != 1:
        raise ValueError('Expected exact regular single-link locked model')
    if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
        raise ValueError('Model descriptor is not read-only')
    if not os.fstatvfs(fd).f_flag & os.ST_RDONLY:
        raise ValueError('Model descriptor filesystem is not read-only')
    if f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}' != mount['major_minor']:
        raise ValueError('Model descriptor is not on the admitted mount')
    return _identity(info)


def _verify_bytes(fd, length, expected_sha, deadline, *, clock=time.monotonic):
    """Pure file-I/O test seam. Production calls only with locked model constants."""
    if type(length) is not int or length < 1 or length > 8 * 1024**3:
        raise ValueError('Invalid bounded model byte count')
    digest = hashlib.sha256()
    offset = 0
    while offset < length:
        if clock() >= deadline:
            raise TimeoutError('Live model verification deadline')
        data = os.pread(fd, min(1024 * 1024, length - offset), offset)
        if not data:
            raise ValueError('Short live model read')
        digest.update(data)
        offset += len(data)
    if clock() >= deadline:
        raise TimeoutError('Live model verification deadline')
    if os.pread(fd, 1, length) or digest.hexdigest() != expected_sha:
        raise ValueError('Live model hash or exact length mismatch')
    return {'sha256': digest.hexdigest(), 'bytes_hashed': offset}


class AdmittedModelFile:
    def __init__(self, fd, identity, mount, report):
        self.fd = fd
        self._identity_json = json.dumps(identity, sort_keys=True)
        self._mount_json = json.dumps(mount, sort_keys=True)
        self.report = report
        self.helper_path = Path(f'/proc/{os.getpid()}/fd/{fd}')

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            os.close(fd)


def admit_model(root, deadline):
    """root is provider-owned and unused: the model location cannot vary."""
    mount = current_mount()
    fd = _open_fixed_model()
    try:
        before = _metadata(fd, mount)
        hashed = _verify_bytes(fd, MODEL_BYTES, MODEL_SHA, deadline)
        if current_mount() != mount or _metadata(fd, mount) != before:
            raise ValueError('Live medium/model identity changed during admission')
        report = {'transport': TRANSPORT, 'path': str(MODEL), 'mount': mount,
                  'file_identity': before, 'fd_access_mode': 'O_RDONLY', **hashed}
        return AdmittedModelFile(fd, before, mount, report)
    except BaseException:
        os.close(fd)
        raise


def recheck_model(block, deadline):
    if type(block) is not AdmittedModelFile or block.fd is None:
        raise ValueError('Admitted live model descriptor is unavailable')
    mount = json.loads(block._mount_json)
    before = json.loads(block._identity_json)
    if current_mount() != mount or _metadata(block.fd, mount) != before:
        raise ValueError('Live medium/model identity changed before posthash')
    hashed = _verify_bytes(block.fd, MODEL_BYTES, MODEL_SHA, deadline)
    if current_mount() != mount or _metadata(block.fd, mount) != before:
        raise ValueError('Live medium/model identity changed during posthash')
    return {'transport': TRANSPORT, 'path': str(MODEL), 'mount': mount,
            'file_identity': before, 'fd_access_mode': 'O_RDONLY', **hashed}
