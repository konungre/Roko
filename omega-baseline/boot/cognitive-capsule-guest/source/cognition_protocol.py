"""Finite JSON data contract, shared by 3.13 controller and isolated 3.12 worker.

No source fragments, module names, filenames, functions or actions are accepted.
Hashes establish identity/integrity, not authentication or truth.
"""
import hashlib
import json
import re

MAX_REQUEST = 49152
MAX_RESPONSE = 49152
MAX_STDERR = 16384
MAX_RESULT = 999998000001
REQUEST_KEYS = {'version', 'operation', 'task_id', 'goal', 'revision', 'evidence'}
RESPONSE_KEYS = {'version', 'operation', 'task_id', 'revision', 'request_sha256',
                 'evidence', 'counts', 'answer', 'authorizes_actions', 'executed_actions'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def decode(raw, cap):
    if type(raw) is not bytes or not 1 <= len(raw) <= cap:
        raise ValueError('JSON byte budget exceeded or empty')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid UTF-8 or excessive JSON nesting') from error
    return value


def string(value, cap, label):
    if type(value) is not str or not value:
        raise ValueError('Invalid ' + label)
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError as error:
        raise ValueError('Invalid UTF-8 ' + label) from error
    if size > cap:
        raise ValueError(label + ' exceeds UTF-8 byte budget')
    return value


def arithmetic(text):
    match = re.fullmatch(r'Arithmetic: (-?[0-9]{1,6}) ([+*-]) (-?[0-9]{1,6})\.', text)
    if match is None:
        raise ValueError('Unsupported arithmetic evidence grammar')
    return int(match[1]), match[2], int(match[3])


def validate_request(value):
    if type(value) is not dict or set(value) != REQUEST_KEYS:
        raise ValueError('Invalid request schema')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid protocol version')
    if type(value['operation']) is not str or value['operation'] not in ('roundtrip', 'arithmetic'):
        raise ValueError('Unsupported fixed operation')
    string(value['task_id'], 512, 'task ID')
    if len(value['task_id']) > 128:
        raise ValueError('Task ID exceeds character limit')
    string(value['goal'], 8000, 'goal')
    if len(value['goal']) > 2000:
        raise ValueError('Goal exceeds character limit')
    if type(value['revision']) is not int or not 1 <= value['revision'] <= 2**53 - 1:
        raise ValueError('Invalid state revision')
    evidence = value['evidence']
    if type(evidence) is not dict or set(evidence) != {'id', 'source', 'text', 'sha256'}:
        raise ValueError('Invalid evidence schema')
    if type(evidence['id']) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', evidence['id']) is None:
        raise ValueError('Invalid evidence ID')
    string(evidence['source'], 4000, 'evidence provenance')
    string(evidence['text'], 32000, 'evidence text')
    if len(evidence['source']) > 1000 or len(evidence['text']) > 8000:
        raise ValueError('Evidence exceeds controller character limits')
    if type(evidence['sha256']) is not str or evidence['sha256'] != hashlib.sha256(evidence['text'].encode('utf-8')).hexdigest():
        raise ValueError('Evidence digest mismatch')
    if value['operation'] == 'arithmetic':
        arithmetic(evidence['text'])
    raw = canonical(value)
    if len(raw) > MAX_REQUEST:
        raise ValueError('Encoded request exceeds byte budget')
    return decode(raw, MAX_REQUEST)


def parse_request(raw):
    return validate_request(decode(raw, MAX_REQUEST))


def response(request, answer):
    request = validate_request(request)
    if request['operation'] == 'arithmetic':
        if type(answer) is not int or abs(answer) > MAX_RESULT:
            raise ValueError('Invalid native integer answer')
    elif answer is not None:
        raise ValueError('Roundtrip must not claim an arithmetic result')
    result = {key: request[key] for key in ('version', 'operation', 'task_id', 'revision', 'evidence')}
    result.update(request_sha256=digest(request), counts=[0, 1, 0], answer=answer,
                  authorizes_actions=False, executed_actions=0)
    if len(canonical(result)) > MAX_RESPONSE:
        raise ValueError('Encoded response exceeds byte budget')
    return result


def validate_response(raw, request):
    request = validate_request(request)
    value = decode(raw, MAX_RESPONSE)
    if type(value) is not dict or set(value) != RESPONSE_KEYS:
        raise ValueError('Invalid response schema')
    expected = response(request, value['answer'])
    # Canonical comparison distinguishes bool from integer and catches all identity drift.
    if canonical(value) != canonical(expected):
        raise ValueError('Response identity, revision, memory counts or authority mismatch')
    return value
