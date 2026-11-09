"""Bounded native bank bridge. No scores or focus are calculated in Python.

Only validated integers enter fixed templates. User IDs are data and mapped to
controller-generated symbols. Native mutation expressions are never dispatched.
"""
import hashlib
import json
import math
import sys
from paths import PRIVATE, ECAN_LOCK, MODULES
from ecan_guest_contract import canonical, parse_request, response_from_native, MAX_REQUEST
from runtime_guard import runtime_maps

_request = None
_imports, _rows, _mutations = [], [], []
_focus = _funds = None

def initialize():
    global _request
    if _request is not None:
        raise ValueError('One request per fresh native process')
    request = parse_request(sys.stdin.buffer.read(MAX_REQUEST + 1))
    raw = ECAN_LOCK.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'c2a4798f6d67c6cf46fee10e0d632a8516e54dbeedf93b8e3337e548facd7fc4':
        raise ValueError('ECAN source lock changed')
    pins = json.loads(raw)['files']
    for name in MODULES:
        path = PRIVATE / name
        if path.resolve() != path or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pins[name]:
            raise ValueError('ECAN source bytes or resolved path changed')
    _request = request
    return True

def ready():
    if _request is None:
        raise ValueError('Native request not initialized')

def module_paths():
    ready()
    return [str(PRIVATE / name) for name in MODULES]

def imported(path):
    expected = module_paths()
    if type(path) is not str or len(_imports) >= len(expected) or path != expected[len(_imports)]:
        raise ValueError('Unexpected import identity or order')
    _imports.append(path)
    return True

def indices():
    ready()
    return list(range(len(_request['candidates'])))

def capacity():
    ready()
    return _request['focus_capacity']

def row(index):
    ready()
    if type(index) is not int or index not in indices():
        raise ValueError('Invalid row index')
    value = _request['candidates'][index]
    return [value[k] for k in ('sti', 'lti', 'stimulus')]

def mutation(term):
    ready()
    if type(term) is not str or len(term.encode('utf-8')) > 4096 or len(_mutations) >= 2 * len(indices()):
        raise ValueError('Invalid native mutation observation')
    # This is an observation, not a success receipt. Later native score/funds
    # checks establish the state change; the optional logger remains unevaluated.
    _mutations.append(term)
    return True

def number(value):
    if type(value) not in (int, float) or not 0 <= value <= 100000 or not math.isfinite(value):
        raise ValueError('Native value is not a finite bounded number')

def score(index, sti, lti):
    ready()
    if type(index) is not int or index != len(_rows) or index not in indices():
        raise ValueError('Invalid native score callback order')
    number(sti); number(lti)
    _rows.append({'index': index, 'sti': sti, 'lti': lti})
    return True

def focus_and_funds(symbols, sti, lti):
    global _focus, _funds
    ready()
    allowed = [f'ecan_atom_{i}' for i in indices()]
    if _focus is not None or type(symbols) is not list or len(symbols) > min(capacity(), len(allowed)):
        raise ValueError('Invalid focus callback')
    if any(type(x) is not str or x not in allowed for x in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError('Unknown or duplicate native focus symbol')
    number(sti); number(lti)
    _focus, _funds = list(symbols), {'sti': sti, 'lti': lti}
    return True

def finish():
    ready()
    if _imports != module_paths() or len(_rows) != len(indices()) or len(_mutations) != 2 * len(indices()) or _focus is None:
        raise ValueError('Incomplete native bank response')
    response = response_from_native(_request, _rows, [int(s.removeprefix('ecan_atom_')) for s in _focus], _funds)
    packet = {'version': 1, 'request': _request, 'response': response,
        'strict_imports': list(MODULES), 'direct_native_focus_symbols': _focus,
        'mutation_return_terms': _mutations, 'runtime': runtime_maps(),
        'executed_actions': 0, 'optional_csv_logger_imported': False}
    raw = canonical(packet)
    if len(raw) > 32768:
        raise ValueError('Native packet exceeds 32KiB')
    return raw.decode('utf-8')
