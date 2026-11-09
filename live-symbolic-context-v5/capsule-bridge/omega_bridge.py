"""Fixed Janus data bridge. Only worker.pl calls these functions.

Evidence crosses into MeTTa as a string value. It is never parsed as source.
"""
import sys
from cognition_protocol import (MAX_REQUEST, canonical, parse_request,
                                response)

_request = None
_roundtrip_checked = False


def initialize():
    global _request, _roundtrip_checked
    if _request is not None:
        raise ValueError('A worker handles exactly one request')
    _request = parse_request(sys.stdin.buffer.read(MAX_REQUEST + 1))
    if _request['operation'] != 'roundtrip':
        raise ValueError('Only bounded literal evidence roundtrip is admitted')
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
        raise ValueError('Operation before memory identity check')
    return _request['operation']


def finish(answer):
    if not _roundtrip_checked:
        raise ValueError('Missing actual Omega message roundtrip')
    if _request['operation'] == 'roundtrip':
        if answer != 'roundtrip-only':
            raise ValueError('Invalid roundtrip sentinel')
        answer = None
    return canonical(response(_request, answer)).decode('utf-8')


def runtime_attestation():
    from runtime_guard import runtime_maps
    import json
    report = runtime_maps()
    sys.stderr.write('ROKO_SYMBOLIC_RUNTIME ' + json.dumps(report, sort_keys=True) + '\n')
    sys.stderr.flush()
    return True
