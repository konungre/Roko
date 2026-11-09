"""Fixed Janus bridge. Never computes substitute native rows or accepts code."""
import errno
import hashlib
import json
import socket
import sys
from paths import ROOT,UPSTREAM,MODULES
from contract import MAX_REQUEST,canonical,parse_request,input_values,response_from_rows
from runtime_guard import runtime_maps

_request=None
_imports=[]
_rows=[]
_network=False

def initialize():
    global _request,_network
    if _request is not None:raise ValueError('One request per fresh process')
    lock=json.loads((ROOT/'upstream-lock.json').read_bytes())
    if lock['commit']!='945e2f83711b143e3f6e2eb112cc40c4f531c6f2':raise ValueError('NARS pin changed')
    for row in lock['files']:
        p=ROOT/row['local_path']
        if p.resolve()!=p or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('NARS source changed')
    _request=parse_request(sys.stdin.buffer.read(MAX_REQUEST+1))
    try:
        s=socket.socket()
    except OSError as e:
        if e.errno!=errno.EPERM:raise
        _network=True
    else:
        s.close();raise ValueError('Network denial control failed')
    return True

def module_paths():return [str(UPSTREAM/name) for name in MODULES]

def imported(path):
    if _request is None or len(_imports)>=2 or path!=module_paths()[len(_imports)]:raise ValueError('Fixed import order')
    _imports.append(path);return True

def values():
    if _request is None or _imports!=module_paths():raise ValueError('Missing fixed sources')
    return input_values(_request)

def observed(a,b,f,c):
    if _imports!=module_paths() or len(_rows)>=2:raise ValueError('Out of order/native result cap')
    _rows.append({'subject_index':a,'predicate_index':b,'frequency':f,'confidence':c})
    return True

def finish():
    if _request is None or _imports!=module_paths() or len(_rows)!=2:raise ValueError('Incomplete native inference')
    packet={'version':1,'request':_request,'strict_imports':list(MODULES),'native_rows':_rows,
      'response':response_from_rows(_request,_rows),'runtime':runtime_maps(),'network_denial_observed':_network}
    raw=canonical(packet)
    if len(raw)>16384:raise ValueError('Packet cap')
    return raw.decode('utf-8')
