"""Native callbacks. Records real MeTTa results; never computes substitute scores."""
import hashlib
import json
import math
import sys
from contract import MAX_BYTES, canonical, parse_request, expressions, response_from_native
from helper_probes import PROBES
from paths import IMPORTS, ROOT
from runtime_guard import runtime_maps

_request=None
_imports=[]
_scores=[]
_probes=[]
_selection=None
_delta=None

def initialize():
    global _request
    if _request is not None: raise ValueError('Exactly one fresh request')
    _request=parse_request(sys.stdin.buffer.read(MAX_BYTES+1))
    lock=json.loads((ROOT/'proof/upstream-lock.json').read_bytes())
    for name,row in lock['files'].items():
        p=ROOT/name
        if p.resolve()!=p or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Upstream bytes changed')
    return True

def ready():
    if _request is None: raise ValueError('Request not initialized')

def module_paths():
    ready();return [str(p) for p in IMPORTS]

def imported(path):
    if len(_imports)>=len(IMPORTS) or path!=module_paths()[len(_imports)]: raise ValueError('Strict import order')
    _imports.append(path);return True

def score_expressions():
    ready();return expressions(_request)['scores']

def decision_expression(kind):
    ready()
    if kind not in ('selected','delta'): raise ValueError('Fixed operation required')
    return expressions(_request)[kind]

def probe_expressions():
    ready();return [row[1] for row in PROBES]

def probe_index():
    ready();return len(_probes)

def score_index():
    ready();return len(_scores)

def near(value,expected):
    if type(expected) is list:
        return type(value) is list and len(value)==len(expected) and all(near(x,y) for x,y in zip(value,expected))
    return type(value) in (int,float) and math.isfinite(value) and math.isclose(value,expected,rel_tol=1e-10,abs_tol=1e-10)

def probe(value):
    if len(_probes)>=len(PROBES) or not near(value,PROBES[len(_probes)][2]): raise ValueError('Numeric helper compatibility failure')
    _probes.append({'name':PROBES[len(_probes)][0],'observed':value});return True

def score(value):
    ready()
    if type(value) not in (int,float) or not math.isfinite(value) or not -30<=value<=10 or len(_scores)>=len(_request['candidates']):
        raise ValueError('Invalid native MAGUS score')
    _scores.append(value);return True

def selected(symbol,delta):
    global _selection,_delta
    if _selection is not None: raise ValueError('Duplicate selection')
    response_from_native(_request,_scores,symbol,delta)
    _selection=symbol;_delta=delta;return True

def finish():
    ready()
    if _imports!=module_paths() or len(_probes)!=len(PROBES) or _selection is None: raise ValueError('Incomplete native computation')
    response=response_from_native(_request,_scores,_selection,_delta)
    result={'version':1,'request':_request,'response':response,'strict_imports':module_paths(),
            'native_selection_symbol':_selection,'native_scores':_scores,'native_delta':_delta,
            'helper_probes':_probes,'runtime':runtime_maps(),'executed_actions':0}
    raw=canonical(result)
    if len(raw)>32768: raise ValueError('Native packet cap')
    return raw.decode()
