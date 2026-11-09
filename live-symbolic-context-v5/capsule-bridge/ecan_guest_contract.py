"""ECAN v1 finite wire contract, not an ECAN implementation or runtime proof.

Only a separately admitted fresh native worker may supply scores. This module
does not approximate ECAN, execute anything, grant permission, or change state.
SHA256 binds detached data; it does not authenticate a worker or establish truth.
"""
import hashlib
import json
import math
import re

OPERATION = 'ecan_rank_v1'
MAX_REQUEST = 16384
MAX_RESPONSE = 32768
MAX_REVISION = 2**53 - 1
MAX_CANDIDATES = 16
REQUEST_KEYS = {'version', 'operation', 'task_id', 'revision', 'snapshot_sha256',
                'request_sha256', 'candidates', 'focus_capacity', 'selection_count'}
IDENTITY_KEYS = ('version', 'operation', 'task_id', 'revision',
                 'snapshot_sha256', 'request_sha256')
RESPONSE_KEYS = set(IDENTITY_KEYS) | {'rows', 'focus', 'ranking', 'selection', 'funds',
                                    'advisory_only', 'authorizes_actions',
                                    'persistent_state_changed'}


class ECANContractError(ValueError):
    """Reject this gate without substituting scores or partial advice."""


def require(condition, message):
    if not condition:
        raise ECANContractError(message)


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ECANContractError('Invalid canonical JSON data') from error


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def _integer_token(token):
    require(len(token) <= 20, 'Oversize JSON integer')
    return int(token)


def _nonfinite(_):
    raise ECANContractError('Nonfinite JSON number')


def decode(raw, cap):
    require(type(raw) is bytes and 1 <= len(raw) <= cap, 'Invalid JSON byte budget')
    try:
        text = raw.decode('utf-8')
        # Bound nesting before json.loads; quoted braces and escapes are data.
        depth = 0
        quoted = escaped = False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in '[{':
                depth += 1
                require(depth <= 12, 'Excessive JSON nesting')
            elif char in ']}':
                depth -= 1
        return json.loads(text, object_pairs_hook=_unique,
                          parse_int=_integer_token, parse_constant=_nonfinite)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ECANContractError('Invalid complete UTF-8 JSON document') from error


def exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), 'Invalid ' + label + ' schema')


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, 'Invalid ' + label)
    return value


def string(value, chars, label):
    require(type(value) is str and 1 <= len(value) <= chars, 'Invalid ' + label)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ECANContractError('Invalid UTF-8 ' + label) from error
    return value


def sha256(value, label):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
            'Invalid ' + label)
    return value


def candidate_id(value):
    require(type(value) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,31}', value) is not None,
            'Invalid candidate ID')
    return value


def validate_candidates(value):
    require(type(value) is list and 1 <= len(value) <= MAX_CANDIDATES,
            'Expected 1..16 candidate records')
    seen = set()
    safe = []
    for item in value:
        exact(item, {'id', 'sti', 'lti', 'stimulus'}, 'candidate')
        identifier = candidate_id(item['id'])
        require(identifier not in seen, 'Duplicate candidate ID')
        seen.add(identifier)
        for key, maximum in (('sti', 1000), ('lti', 1000), ('stimulus', 10)):
            integer(item[key], 0, maximum, key)
        safe.append(dict(item))
    return sorted(safe, key=lambda item: item['id'])


def make_request(*, task_id, revision, snapshot_sha256, candidates: list,
                 focus_capacity, selection_count):
    ordered = validate_candidates(candidates)
    # Bound direct Python inputs before serializing/hashing them too.
    string(task_id, 128, 'task ID')
    integer(revision, 1, MAX_REVISION, 'revision')
    sha256(snapshot_sha256, 'snapshot digest')
    integer(focus_capacity, 1, MAX_CANDIDATES, 'focus capacity')
    integer(selection_count, 1, len(ordered), 'selection count')
    body = {'version': 1, 'operation': OPERATION, 'task_id': task_id,
            'revision': revision, 'snapshot_sha256': snapshot_sha256,
            'candidates': ordered, 'focus_capacity': focus_capacity,
            'selection_count': selection_count}
    return validate_request({**body, 'request_sha256': digest(body)})


def validate_request(value):
    exact(value, REQUEST_KEYS, 'request')
    integer(value['version'], 1, 1, 'version')
    require(type(value['operation']) is str and value['operation'] == OPERATION,
            'Unsupported fixed operation')
    string(value['task_id'], 128, 'task ID')
    integer(value['revision'], 1, MAX_REVISION, 'revision')
    sha256(value['snapshot_sha256'], 'snapshot digest')
    sha256(value['request_sha256'], 'request digest')
    ordered = validate_candidates(value['candidates'])
    require(value['candidates'] == ordered, 'Candidates must be in canonical ID order')
    integer(value['focus_capacity'], 1, MAX_CANDIDATES, 'focus capacity')
    integer(value['selection_count'], 1, len(ordered), 'selection count')
    body = {key: item for key, item in value.items() if key != 'request_sha256'}
    require(value['request_sha256'] == digest(body), 'Request digest mismatch')
    return decode(canonical(value), MAX_REQUEST)


def parse_request(raw):
    return validate_request(decode(raw, MAX_REQUEST))


def source_ops(request):
    """Data for fixed native calls; neither IDs nor text enter executable source.

    Do not execute this as a replacement for the admitted native worker. The
    worker must perform real setAv/stimulate/getter/bank/focus calls.
    """
    request = validate_request(request)
    return tuple((f'ecan_atom_{index}', row['sti'], row['lti'], row['stimulus'])
                 for index, row in enumerate(request['candidates']))


def _number(value, maximum, label):
    # Check bounds before isfinite so giant integers cannot overflow conversion.
    require(type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value),
            'Invalid ' + label)
    return value


def _id_list(value, admitted, label, length=None):
    require(type(value) is list and len(value) <= len(admitted), 'Invalid ' + label)
    if length is not None:
        require(len(value) == length, 'Incomplete ' + label)
    require(all(type(item) is str and item in admitted for item in value),
            'Unknown ' + label + ' identity')
    require(len(set(value)) == len(value), 'Duplicate ' + label + ' identity')


def validate_response(raw, request):
    request = validate_request(request)
    value = decode(raw, MAX_RESPONSE)
    exact(value, RESPONSE_KEYS, 'response')
    require(canonical({key: value[key] for key in IDENTITY_KEYS}) ==
            canonical({key: request[key] for key in IDENTITY_KEYS}),
            'Response identity, revision or digest mismatch')
    require(value['advisory_only'] is True and value['authorizes_actions'] is False
            and value['persistent_state_changed'] is False, 'Invalid advisory authority')
    admitted = [row['id'] for row in request['candidates']]
    rows = value['rows']
    require(type(rows) is list and len(rows) == len(admitted), 'Incomplete indexed scores')
    seen = set()
    for row in rows:
        exact(row, {'index', 'id', 'sti', 'lti', 'in_focus'}, 'indexed score')
        index = integer(row['index'], 0, len(admitted) - 1, 'score index')
        require(index not in seen, 'Duplicate score index')
        seen.add(index)
        require(type(row['id']) is str and row['id'] == admitted[index], 'Score ID/index mismatch')
        _number(row['sti'], 1200, 'score STI')
        _number(row['lti'], 1200, 'score LTI')
        require(type(row['in_focus']) is bool, 'Invalid in-focus flag')
    _id_list(value['focus'], admitted, 'focus')
    require(len(value['focus']) <= min(request['focus_capacity'], len(admitted)),
            'Focus exceeds capacity')
    for row in rows:
        require(row['in_focus'] == (row['id'] in value['focus']), 'Focus flag mismatch')
    exact(value['funds'], {'sti', 'lti'}, 'funds')
    for key in ('sti', 'lti'):
        _number(value['funds'][key], 100000, 'funds ' + key)
        require(abs(math.fsum([value['funds'][key]] + [row[key] for row in rows]) - 100000) <= 1e-6,
                'Attention-bank conservation failed for ' + key)
    expected = [row['id'] for row in sorted(rows, key=lambda item: (-item['sti'], -item['lti'], item['id']))]
    _id_list(value['ranking'], admitted, 'ranking', len(admitted))
    _id_list(value['selection'], admitted, 'selection', request['selection_count'])
    require(value['ranking'] == expected, 'Claimed ranking differs from controller sort')
    require(value['selection'] == expected[:request['selection_count']], 'Top-k substitution')
    # Preserve native focus membership/order separately from deterministic rank.
    return value


def response_from_native(request, rows, focus, funds):
    """Serialize typed native callback data, never synthesize native scores.

    rows: exactly N {index, sti, lti} dictionaries; focus: native integer indices;
    funds: {sti, lti}. These input values MUST come from actual admitted calls.
    Calling this function alone provides no native provenance or attestation.
    """
    request = validate_request(request)
    count = len(request['candidates'])
    require(type(rows) is list and len(rows) == count, 'Incomplete native rows')
    require(type(focus) is list and len(focus) <= min(count, request['focus_capacity']),
            'Invalid native focus')
    for index in focus:
        integer(index, 0, count - 1, 'native focus index')
    require(len(set(focus)) == len(focus), 'Duplicate native focus index')
    mapped = []
    for row in rows:
        exact(row, {'index', 'sti', 'lti'}, 'native row')
        index = integer(row['index'], 0, count - 1, 'native row index')
        _number(row['sti'], 1200, 'native STI')
        _number(row['lti'], 1200, 'native LTI')
        mapped.append({**row, 'id': request['candidates'][index]['id'], 'in_focus': index in focus})
    ranking = [row['id'] for row in sorted(mapped, key=lambda item: (-item['sti'], -item['lti'], item['id']))]
    result = {key: request[key] for key in IDENTITY_KEYS}
    result.update(rows=sorted(mapped, key=lambda item: item['index']),
                  focus=[request['candidates'][index]['id'] for index in focus],
                  ranking=ranking, selection=ranking[:request['selection_count']], funds=funds,
                  advisory_only=True, authorizes_actions=False, persistent_state_changed=False)
    return validate_response(canonical(result), request)
