#!/usr/bin/python3.13
"""Guest-only inert transport proof; never load or generate model output."""
import errno
import json
import os
from pathlib import Path
import sys
import time

from raw_transport import admit, validate_spec
from synthetic import specification


def probe():
    expected = specification()
    supplied = json.loads((Path(__file__).parent / 'synthetic.lock.json').read_text())
    if supplied != expected:
        raise ValueError('Unexpected synthetic manifest')
    admitted = admit(expected, time.monotonic() + 30, production=False, check_mmap=True)
    try:
        # O_RDONLY alone must reject writes even before device-level enforcement.
        try:
            os.pwrite(admitted.fd, b'X', 0)
        except OSError as error:
            if error.errno != errno.EBADF:
                raise
            fd_write = {'rejected': True, 'errno': error.errno}
        else:
            raise ValueError('O_RDONLY descriptor accepted write')
        # Independently test the read-only virtual device. This function accepts
        # only the exact inert fixture serial/hash, never the production model.
        path = '/dev/' + admitted.record['name']
        writable = None
        try:
            writable = os.open(path, os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            os.pwrite(writable, b'X', 0)
        except OSError as error:
            if error.errno not in (errno.EROFS, errno.EACCES, errno.EPERM):
                raise
            device_write = {'rejected': True, 'errno': error.errno}
        else:
            raise ValueError('Read-only synthetic block accepted write')
        finally:
            if writable is not None:
                os.close(writable)
        negatives = {}
        for key, wrong in [('serial', 'roko-wrong-synthetic'), ('capacity_bytes', expected['capacity_bytes'] + 512)]:
            changed = dict(expected, **{key: wrong})
            try:
                item = admit(changed, time.monotonic() + 5, production=False)
            except ValueError as error:
                negatives[key] = str(error)
            else:
                item.close()
                raise ValueError('Negative transport case was admitted: ' + key)
        # Re-read the original prefix after the attempted writes.
        from raw_transport import verify_bytes
        after = verify_bytes(admitted.fd, expected, time.monotonic() + 30, check_mmap=True)
        return {'passed': True, 'fixture': expected, 'record': admitted.record,
                'checks': admitted.report, 'readonly_fd_write': fd_write,
                'readonly_device_write': device_write, 'negative_cases': negatives,
                'after_write_checks': after, 'uptime': Path('/proc/uptime').read_text().strip(),
                'model_attached': False, 'model_loaded': False, 'external_actions': 0}
    finally:
        admitted.close()


if __name__ == '__main__':
    try:
        receipt = probe()
    except BaseException as error:
        receipt = {'passed': False, 'error': type(error).__name__ + ': ' + str(error),
                   'model_attached': False, 'model_loaded': False}
    print('ROKO_RAW_SYNTHETIC_RESULT ' + json.dumps(receipt, sort_keys=True), flush=True)
    sys.exit(0 if receipt['passed'] else 1)
