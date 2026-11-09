"""Explicit Linux read-only virtio block admission; never a regular-file fallback.

This is a separate candidate transport. Host unit tests cannot admit a guest.
"""
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import stat
import struct
import time

SECTOR = 512
BLKROGET = 0x125e
BLKGETSIZE64 = 0x80081272  # Linux x86-64 guest ABI, unsigned long long.
MODEL_BYTES = 4230976352
MODEL_SHA = '5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
TRANSPORT = 'virtio-blk-raw-readonly-v1'


def capacity(length):
    if type(length) is not int or not 0 < length <= 8 * 1024**3:
        raise ValueError('Invalid bounded source length')
    return (length + SECTOR - 1) // SECTOR * SECTOR


def validate_spec(spec, production=True):
    keys = {'transport', 'serial', 'source_bytes', 'capacity_bytes', 'sha256', 'zero_tail_bytes', 'logical_block_size'}
    if not isinstance(spec, dict) or not keys <= set(spec) or spec['transport'] != TRANSPORT:
        raise ValueError('Wrong explicit block transport')
    if (not isinstance(spec['serial'], str) or not re.fullmatch(r'roko-[a-z-]{1,30}', spec['serial'])
            or not isinstance(spec['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', spec['sha256'])):
        raise ValueError('Invalid serial or digest')
    expected = capacity(spec['source_bytes'])
    if (type(spec['capacity_bytes']) is not int or spec['capacity_bytes'] != expected
            or type(spec['zero_tail_bytes']) is not int or spec['zero_tail_bytes'] != expected - spec['source_bytes']
            or type(spec['logical_block_size']) is not int or spec['logical_block_size'] != SECTOR):
        raise ValueError('Inconsistent sector geometry')
    if production:
        if (spec.get('status') != 'raw-model-transport-admitted'
                or spec.get('reviewed_admission') is not True
                or not isinstance(spec.get('synthetic_receipt_sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', spec['synthetic_receipt_sha256'])
                or spec['synthetic_receipt_sha256'] == '0' * 64):
            raise ValueError('Raw model awaits synthetic guest proof and reviewed admission')
        if (spec['serial'] != 'roko-granite-model' or spec['source_bytes'] != MODEL_BYTES
                or spec['sha256'] != MODEL_SHA):
            raise ValueError('Unexpected locked model')
    return spec


def read_record(device):
    """Read the actual kernel identity; no udev alias or mount lookup."""
    return {'name': device.name, 'serial': (device / 'serial').read_text().strip(),
            'sectors': int((device / 'size').read_text()), 'readonly': int((device / 'ro').read_text()),
            'dev': (device / 'dev').read_text().strip(),
            'logical_block_size': int((device / 'queue/logical_block_size').read_text()),
            'driver': str((device / 'device/driver').resolve(strict=True)),
            'subsystem': str((device / 'device/subsystem').resolve(strict=True)),
            'partitions': sorted(p.name for p in device.glob(device.name + '[0-9]*'))}


def validate_record(record, spec):
    if (not re.fullmatch(r'vd[a-z]+', record['name']) or record['serial'] != spec['serial']
            or record['readonly'] != 1 or record['sectors'] * SECTOR != spec['capacity_bytes']
            or record['logical_block_size'] != SECTOR or record['partitions']
            or record['driver'] != '/sys/bus/virtio/drivers/virtio_blk'
            or record['subsystem'] != '/sys/bus/virtio'
            or not re.fullmatch(r'[0-9]+:[0-9]+', record['dev'])):
        raise ValueError('Unexpected block identity, geometry, driver or read-only state')
    return record


def discover(spec, sysroot=Path('/sys/block')):
    matches = []
    for device in sysroot.iterdir():
        if not re.fullmatch(r'vd[a-z]+', device.name):
            continue
        try:
            serial = (device / 'serial').read_text().strip()
        except FileNotFoundError:
            continue
        if serial == spec['serial']:
            matches.append(device)
    if len(matches) != 1:
        raise ValueError('Expected exactly one declared virtio block serial')
    return validate_record(read_record(matches[0]), spec)


def verify_bytes(fd, spec, deadline, check_mmap=False):
    """Prefix hash and zero-tail checks deliberately use capacity, not st_size."""
    digest = hashlib.sha256()
    offset = 0
    while offset < spec['source_bytes']:
        if time.monotonic() >= deadline:
            raise TimeoutError('Raw block verification deadline exceeded')
        data = os.pread(fd, min(1024 * 1024, spec['source_bytes'] - offset), offset)
        if not data:
            raise ValueError('Short raw block model prefix')
        offset += len(data)
        digest.update(data)
    if digest.hexdigest() != spec['sha256']:
        raise ValueError('Raw block model prefix hash mismatch')
    tail = os.pread(fd, spec['zero_tail_bytes'], spec['source_bytes'])
    if tail != b'\0' * spec['zero_tail_bytes']:
        raise ValueError('Raw block tail is not exact zero padding')
    end = os.lseek(fd, 0, os.SEEK_END)
    if end != spec['capacity_bytes']:
        raise ValueError('Unexpected block SEEK_END')
    os.lseek(fd, 0, os.SEEK_SET)
    report = {'prefix_sha256': digest.hexdigest(), 'prefix_bytes_hashed': offset,
              'zero_tail_bytes': len(tail), 'seek_end': end, 'mmap_checked': False}
    if check_mmap:
        # Small synthetic fixture only. Production llama owns its full mapping.
        if spec['capacity_bytes'] > 2 * 1024**2:
            raise ValueError('Synthetic mmap probe size cap')
        with mmap.mmap(fd, spec['capacity_bytes'], flags=mmap.MAP_SHARED, prot=mmap.PROT_READ) as view:
            if hashlib.sha256(view[:spec['source_bytes']]).hexdigest() != spec['sha256']:
                raise ValueError('mmap prefix mismatch')
            if view[spec['source_bytes']:] != b'\0' * spec['zero_tail_bytes']:
                raise ValueError('mmap tail mismatch')
        report['mmap_checked'] = True
    return report


class AdmittedBlock:
    def __init__(self, fd, record, report):
        self.fd, self.record, self.report = fd, record, report
        # Open the pinned parent descriptor, not a mutable /dev path. Native and
        # supervisor need not inherit it; the live provider owns its lifetime.
        self.helper_path = Path(f'/proc/{os.getpid()}/fd/{fd}')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def admit(spec, deadline, production=True, check_mmap=False):
    validate_spec(spec, production)
    record = discover(spec)
    fd = os.open('/dev/' + record['name'], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        observed = os.fstat(fd)
        major, minor = map(int, record['dev'].split(':'))
        if not stat.S_ISBLK(observed.st_mode) or observed.st_rdev != os.makedev(major, minor):
            raise ValueError('Device descriptor does not match sysfs')
        access = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        ro = struct.unpack('i', fcntl.ioctl(fd, BLKROGET, b'\0' * 4))[0]
        size = struct.unpack('Q', fcntl.ioctl(fd, BLKGETSIZE64, b'\0' * 8))[0]
        if access != os.O_RDONLY or ro != 1 or size != spec['capacity_bytes']:
            raise ValueError('Block descriptor is not the admitted read-only capacity')
        report = verify_bytes(fd, spec, deadline, check_mmap)
        # Recheck kernel identity after reading, fail closed on reconfiguration.
        if discover(spec) != record:
            raise ValueError('Block identity changed during verification')
        report.update(fd_access_mode='O_RDONLY', blkroget=ro, blkgetsize64=size,
                      device_fstat_size=observed.st_size, rdev=f'{major}:{minor}')
        return AdmittedBlock(fd, record, report)
    except BaseException:
        os.close(fd)
        raise


def admit_model(root, deadline):
    spec = json.loads((root / 'granite-raw-transport.lock.json').read_text())
    return admit(spec, deadline)
