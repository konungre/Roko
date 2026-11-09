"""Typed finite MAGUS proposal contract. Validation does not execute MetaMo."""
from decimal import Decimal
import hashlib
import json
import math
import re

MAX_BYTES = 16384
MAX_CANDIDATES = 8
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def decode(raw, cap=MAX_BYTES):
    if type(raw) is not bytes or not 1 <= len(raw) <= cap:
        raise ValueError('JSON byte cap')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject(value): raise ValueError('Non-finite JSON constant')
    try:
        return json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                          parse_constant=reject)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Malformed JSON') from exc

def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('Unexpected object fields')

def number(value, low, high, *, quantized=True):
    if type(value) not in (float, int) or not low <= value <= high or not math.isfinite(value):
        raise ValueError('Finite numeric domain required')
    if quantized and Decimal(str(value)) * 1000000 != (Decimal(str(value)) * 1000000).to_integral_value():
        raise ValueError('At most six decimal places')
    return value

def vector(value, length, low, high):
    if type(value) is not list or len(value) != length: raise ValueError('Vector shape')
    for x in value: number(x, low, high)
    return value

def identifier(value):
    if type(value) is not str or not ID.fullmatch(value): raise ValueError('Identifier domain')
    return value

def parse_request(raw):
    request = decode(raw)
    keys(request, ('version', 'request_id', 'operation', 'state', 'candidates'))
    if type(request['version']) is not int or request['version'] != 1 or request['operation'] != 'rank_proposals':
        raise ValueError('Unsupported request version or operation')
    identifier(request['request_id'])
    keys(request['state'], ('goals', 'modulators'))
    vector(request['state']['goals'], 8, 0, 1)
    vector(request['state']['modulators'], 6, 0, 1)
    candidates = request['candidates']
    if type(candidates) is not list or not 1 <= len(candidates) <= MAX_CANDIDATES: raise ValueError('Candidate count')
    ids = []
    for row in candidates:
        keys(row, ('id', 'correlations', 'risk', 'delta_goals'))
        ids.append(identifier(row['id']))
        vector(row['correlations'], 8, -1, 1)
        vector(row['delta_goals'], 8, -0.1, 0.1)
        number(row['risk'], 0, 1)
    if len(set(ids)) != len(ids): raise ValueError('Duplicate candidate identifiers')
    return request

def request_digest(request):
    return hashlib.sha256(canonical(request)).hexdigest()

def atom_vector(values):
    return '(' + ' '.join(format(float(x), '.6f') for x in values) + ')'

def expressions(request):
    request = parse_request(canonical(request))
    state = '(motivation ' + atom_vector(request['state']['goals']) + ' ' + atom_vector(request['state']['modulators']) + ')'
    actions = ['(action metamo_candidate_%d %s %.6f %s)' %
               (i, atom_vector(row['correlations']), row['risk'], atom_vector(row['delta_goals']))
               for i, row in enumerate(request['candidates'])]
    decision = '(magusDecide %s (%s))' % (state, ' '.join(actions))
    return {'scores': ['!(magusScore %s %s)' % (state, action) for action in actions],
            'selected': '!(actionId (decisionAction %s))' % decision,
            'delta': '!(decisionDeltaG %s)' % decision}

def response_from_native(request, scores, selected_symbol, delta):
    request = parse_request(canonical(request))
    if type(scores) is not list or len(scores) != len(request['candidates']): raise ValueError('Native score count')
    for x in scores: number(x, -30, 10, quantized=False)
    allowed = ['metamo_candidate_%d' % i for i in range(len(scores))]
    if type(selected_symbol) is not str or selected_symbol not in allowed: raise ValueError('Unknown native selection')
    selected = allowed.index(selected_symbol)
    # The source uses strict >, retaining the first candidate for equal scores.
    if selected != max(range(len(scores)), key=scores.__getitem__): raise ValueError('Native selection/score disagreement')
    vector(delta, 8, -0.1, 0.1)
    if delta != request['candidates'][selected]['delta_goals']: raise ValueError('Native delta changed')
    return {'version': 1, 'request_sha256': request_digest(request),
            'scores': [{'id': row['id'], 'score': score} for row, score in zip(request['candidates'], scores)],
            'selected_proposal_id': request['candidates'][selected]['id'],
            'proposed_delta_goals': delta, 'authorizes_actions': False, 'executed_actions': 0,
            'state_changed': False, 'scope': 'upstream-magus-decision-subset'}

def validate_response(raw, request):
    value = decode(raw)
    keys(value, ('version','request_sha256','scores','selected_proposal_id','proposed_delta_goals',
                 'authorizes_actions','executed_actions','state_changed','scope'))
    rows = value['scores']
    if type(rows) is not list or len(rows) != len(request['candidates']): raise ValueError('Response rows')
    for i, row in enumerate(rows):
        keys(row, ('id', 'score'))
        if row['id'] != request['candidates'][i]['id']: raise ValueError('Response identity/order')
    ids = [row['id'] for row in request['candidates']]
    if value['selected_proposal_id'] not in ids: raise ValueError('Unknown selected identifier')
    expected = response_from_native(request, [x['score'] for x in rows],
        'metamo_candidate_%d' % ids.index(value['selected_proposal_id']), value['proposed_delta_goals'])
    if canonical(value) != canonical(expected): raise ValueError('Response authority or shape changed')
    return value
