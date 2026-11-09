"""Fixed per-component controller process isolates legacy module import names."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[2]


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
    if len(sys.argv)!=7:raise ValueError('Fixed component/profile/evidence arguments')
    name,manifest_path,admission,directory,guard_path,guard_admission=sys.argv[1:];directory=Path(directory)
    sys.path.insert(0,str(ROOT))
    from components.nars_hyperon.source.runtime import verify
    guard=json.loads(Path(guard_path).read_bytes());verify(guard,guard_admission)
    if name not in ('metamo','airis','nace','ai_dsl','os_state'):raise ValueError('Unknown component')
    raw=Path(manifest_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=admission:raise ValueError('Component manifest digest')
    manifest=json.loads(raw)
    request_raw=sys.stdin.buffer.read(16385)
    if not 0<len(request_raw)<=16384:raise ValueError('Request cap')
    request=json.loads(request_raw)
    path=(ROOT/'components/os_atomspace/conversation_gateway.py' if name=='os_state' else
          ROOT/'components/ai_dsl/gateway.py' if name=='ai_dsl' else
          ROOT/'components/nace/qualification/run_host_slice.py' if name=='nace' else ROOT/('components/'+name+'_host/qualify.py'))
    spec=importlib.util.spec_from_file_location('fixed_component_gate',path)
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    if name=='os_state':
        response,receipt=gate.run(request,manifest,directory)
    elif name=='ai_dsl':
        manifest=dict(manifest,evidence_root=str(directory))
        response,receipt=gate.run(request,manifest)
    elif name=='metamo':
        from contract import parse_request
        request=parse_request(request_raw)
        scores=[gate.score(request['state'],c) for c in request['candidates']]
        winner=request['candidates'][max(range(len(scores)),key=scores.__getitem__)]['id']
        receipt=gate.run_case('conversation',request,winner,manifest,directory)
        response=receipt['response']
    elif name=='airis':
        from contract import parse_request
        request=parse_request(request_raw)
        receipt=gate.run(request,manifest,directory);response=receipt['response']
    else:
        if manifest['files']!=gate.frozen_files():raise ValueError('NACE pinned files changed')
        # The derived seven-function worker is unchanged; the oracle only checks
        # its actual result, never supplies a native output.
        expected=gate.transition(request,gate.ReferenceCore())
        directory.mkdir(exist_ok=False)
        receipt=gate.run_case({'id':'conversation','request':request,'expected':expected},manifest,directory,time.monotonic()+5)
        if receipt['status']!='passed':raise ValueError('NACE native comparison failed')
        if manifest['files']!=gate.frozen_files():raise ValueError('NACE files changed after execution')
        response=receipt['observed']
    verify(guard,guard_admission)
    print(canonical({'component':name,'request_sha256':hashlib.sha256(canonical(request)).hexdigest(),
        'response':response,'receipt':receipt}).decode())
if __name__=='__main__':main()
