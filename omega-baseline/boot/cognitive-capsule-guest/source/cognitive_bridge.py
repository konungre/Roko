"""Fixed Janus data bridge. Only worker.pl calls these functions.

Evidence crosses into MeTTa as a string value. It is never parsed as source.
"""
import sys
from cognition_protocol import (MAX_REQUEST, arithmetic, canonical, parse_request,
                                response)

_request = None
_roundtrip_checked = False


def initialize():
    global _request, _roundtrip_checked
    if _request is not None:
        raise ValueError('A worker handles exactly one request')
    _request = parse_request(sys.stdin.buffer.read(MAX_REQUEST + 1))
    _roundtrip_checked = False
    return True


def evidence_json():
    if _request is None:
        raise ValueError('Worker is not initialized')
    return canonical(_request).decode('utf-8')


def check_roundtrip(messages):
    global _roundtrip_checked
    if type(messages) is not list or messages != [evidence_json()]:
        raise ValueError('Omega message roundtrip differs from controller snapshot')
    _roundtrip_checked = True
    return True


def operation():
    if not _roundtrip_checked:
        raise ValueError('Arithmetic before memory identity check')
    return _request['operation']


def operator():
    return arithmetic(_request['evidence']['text'])[1]


def left():
    return arithmetic(_request['evidence']['text'])[0]


def right():
    return arithmetic(_request['evidence']['text'])[2]


def finish(answer):
    if not _roundtrip_checked:
        raise ValueError('Missing actual Omega message roundtrip')
    if _request['operation'] == 'roundtrip':
        if answer != 'roundtrip-only':
            raise ValueError('Invalid roundtrip sentinel')
        answer = None
    return canonical(response(_request, answer)).decode('utf-8')


def runtime_attestation():
    """Inspect only this process's executable maps; never follow request paths."""
    from pathlib import Path
    import json
    capsule = Path(__file__).resolve().parents[1]
    if tuple(sys.version_info[:3]) != (3, 12, 14):
        raise ValueError('Unexpected embedded Python ABI/version')
    with open('/proc/self/maps', 'rb') as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError('Native memory-map budget exceeded')
    paths = set()
    for line in raw.decode('utf-8').splitlines():
        fields = line.split(None, 5)
        if len(fields) != 6 or 'x' not in fields[1] or fields[5].startswith('['):
            continue
        path = Path(fields[5])
        if not path.is_absolute() or not path.is_relative_to(capsule):
            raise ValueError('Executable mapping escaped private capsule: ' + str(path))
        paths.add('capsule/' + str(path.relative_to(capsule)))
    required = {'capsule/swipl/bin/x86_64-linux/swipl',
                'capsule/swipl/lib/x86_64-linux/janus.so',
                'capsule/python/lib/libpython3.12.so.1.0'}
    if not required <= paths:
        raise ValueError('Expected actual Janus3.12 mappings missing')
    report = {'python': [3, 12, 14], 'executable_mappings': sorted(paths)}
    sys.stderr.write('ROKO_COGNITIVE_RUNTIME ' + json.dumps(report, sort_keys=True) + '\n')
    sys.stderr.flush()
    return True
