"""Fresh host qualification of fixed upstream MAGUS cases; no action dispatch."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO))
from components.nars_hyperon.source.runtime import sha,tree
sys.path.insert(0,str(ROOT/'source'))
from contract import canonical,response_from_native
from fixtures import cases
from helper_probes import PROBES
from reference_oracle import score
from paths import IMPORTS


def near(a,b):
    if type(b) is list:return type(a) is list and len(a)==len(b) and all(near(x,y) for x,y in zip(a,b))
    return type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10)


def prepare(profile,base):
    files={str(Path(p).resolve()):h for p,h in profile['files'].items()}
    files.update(base['files'])
    roots={str(ROOT/'source'):False,str(ROOT/'upstream'):False}
    roots.update(base['roots'])
    trees={p:tree(p,skip) for p,skip in roots.items()}
    paths=[ROOT/'qualify.py',ROOT/'proof/upstream-lock.json',REPO/'omega-baseline/scripts/no-network.py']
    for root,entries in trees.items():paths.extend(Path(root)/e for e in entries)
    links=dict(base['symlinks'])
    for p in paths:
        if p.is_symlink():links[str(p)]=os.readlink(p)
        if p.is_file():files[str(p.resolve())]=sha(p)
    return dict(schema='roko.metamo.host-probe.v1',profile=profile,files=files,roots=roots,trees=trees,symlinks=links)


def verify(m):
    for root,skip in m['roots'].items():
        if tree(root,skip)!=m['trees'][root]:raise ValueError('Tree changed: '+root)
    for p,target in m['symlinks'].items():
        if not Path(p).is_symlink() or os.readlink(p)!=target:raise ValueError('Link changed: '+p)
    for p,h in m['files'].items():
        if sha(p)!=h:raise ValueError('Bytes changed: '+p)


def check(packet,request,winner,manifest):
    if packet['request']!=request or packet['executed_actions']!=0:raise ValueError('Request/authority mismatch')
    response=response_from_native(request,packet['native_scores'],packet['native_selection_symbol'],packet['native_delta'])
    if response!=packet['response'] or response['selected_proposal_id']!=winner:raise ValueError('Selection mismatch')
    if not near(packet['native_scores'],[score(request['state'],c) for c in request['candidates']]):raise ValueError('Independent score disagreement')
    if packet['strict_imports']!=[str(p) for p in IMPORTS]:raise ValueError('Import mismatch')
    probes=packet['helper_probes']
    if len(probes)!=len(PROBES) or not all(p['name']==expected[0] and near(p['observed'],expected[2]) for p,expected in zip(probes,PROBES)):
        raise ValueError('Independent helper disagreement')
    maps=packet['runtime']['executable_mappings']
    if not maps or any(p not in manifest['files'] for p in maps):raise ValueError('Unpinned executable mapping')
    return response


def run_case(name,request,winner,m,directory):
    verify(m);directory.mkdir(exist_ok=False)
    (directory/'request.json').write_bytes(canonical(request))
    profile=m['profile'];start=time.monotonic();proc=None;streams=[];errors=[];failure=None;response=None
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',**profile['runtime_env'],
        'PETTA_PATH':profile['petta'],'ROKO_METAMO_SOURCE':str(ROOT)}
    env['PYTHONPATH']=str(ROOT/'source')+':'+env['PYTHONPATH']
    try:
        streams=[(directory/'stdout').open('xb'),(directory/'stderr').open('xb')]
        command=[profile['python'],'-B',str(REPO/'omega-baseline/scripts/no-network.py'),
            profile['python'],'-B',str(ROOT/'source/launch.py'),str(os.getpid()),profile['swipl']]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=streams[0],stderr=streams[1],
            cwd=directory,env=env,close_fds=True,start_new_session=True)
        proc.communicate(canonical(request),timeout=10)
    except BaseException as exc:failure=exc
    finally:
        if proc is not None and proc.returncode is None:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as exc:errors.append('kill: '+repr(exc))
            try:proc.wait(timeout=2)
            except BaseException as exc:errors.append('reap: '+repr(exc))
        if proc is not None and proc.stdin is not None:streams.append(proc.stdin)
        for stream in streams:
            try:stream.close()
            except BaseException as exc:errors.append('close: '+repr(exc))
    packet=None
    try:
        if failure is not None:raise failure
        if errors or proc is None or proc.returncode!=0:raise ValueError('Native process/cleanup failed')
        raw=(directory/'stdout').read_bytes()
        if len(raw)>32768:raise ValueError('Packet cap')
        packet=json.loads(raw);response=check(packet,request,winner,m);verify(m)
    except BaseException as exc:failure=exc
    receipt=dict(name=name,status='passed' if failure is None else 'failed',seconds=time.monotonic()-start,
        returncode=None if proc is None else proc.returncode,finalization_errors=errors,
        error=None if failure is None else repr(failure),response=response,executed_actions=0,
        runtime=None if packet is None else packet.get('runtime'))
    (directory/'receipt.json').write_bytes(canonical(receipt)+b'\n')
    if failure is not None:raise failure
    return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--symbolic-profile',type=Path,required=True)
    p.add_argument('--base-manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    m=prepare(json.loads(args.symbolic_profile.read_bytes()),json.loads(args.base_manifest.read_bytes()))
    (args.output/'manifest.json').write_bytes(canonical(m)+b'\n')
    start=time.monotonic();results=[];error=None
    try:
        for name,request,winner in cases():results.append(run_case(name,request,winner,m,args.output/name))
    except BaseException as exc:error=repr(exc)
    result=dict(status='passed' if error is None and len(results)==8 else 'failed',error=error,
        cases=results,seconds=time.monotonic()-start,manifest_sha256=hashlib.sha256(canonical(m)).hexdigest(),
        full_metamo=False,conversation_integrated=False,executed_actions=0)
    (args.output/'result.json').write_bytes(canonical(result)+b'\n')
    print(json.dumps(result,indent=2));return int(result['status']!='passed')

if __name__=='__main__':raise SystemExit(main())
