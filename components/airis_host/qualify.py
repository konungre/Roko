"""Fresh actual AIRIS scalar qualification; historical admission is untouched."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO))
from components.nars_hyperon.source.runtime import sha,tree
sys.path.insert(0,str(ROOT/'source'))
from contract import canonical,decode,observation,validate_packet


def fixture(name,delta,query):
    rows=[observation('evidence_'+str(i),'synthetic:recorded inert transition',before,action,
        before+(delta if action=='step' else 0))
        for i,(before,action) in enumerate(((2,'step'),(4,'step'),(2,'hold'),(4,'hold')))]
    return dict(version=1,operation='learn-scalar-transition',task_id=name,revision=1,training=rows,query=query)
CASES=(('increment',1,7),('decrement',-1,7),('double_step',2,11),('reset_repeat',1,7))


def prepare(base,python):
    lock=json.loads((ROOT/'proof/upstream-lock.json').read_bytes())
    for row in lock['files']:
        data=(ROOT/'upstream'/row['path']).read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('Pinned AIRIS source mismatch')
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=row['git_blob_sha']:
            raise ValueError('Pinned AIRIS Git object mismatch')
    roots={**base['roots'],str(ROOT/'source'):False,str(ROOT/'upstream'):False}
    trees={p:tree(p,skip) for p,skip in roots.items()};files=dict(base['files']);links=dict(base['symlinks'])
    paths=[Path('/usr/lib/x86_64-linux-gnu/libseccomp.so.2'),ROOT/'qualify.py',ROOT/'proof/upstream-lock.json',REPO/'omega-baseline/scripts/no-network.py']
    for root,entries in trees.items():paths.extend(Path(root)/e for e in entries)
    for p in paths:
        if p.is_symlink():links[str(p)]=os.readlink(p)
        if p.is_file():files[str(p.resolve())]=sha(p)
    if str(Path(python).resolve()) not in files:raise ValueError('Python not in closure')
    return dict(schema='roko.airis.host-probe.v1',python=python,files=files,roots=roots,trees=trees,symlinks=links)


def verify(m):
    for root,skip in m['roots'].items():
        if tree(root,skip)!=m['trees'][root]:raise ValueError('Membership changed: '+root)
    for p,target in m['symlinks'].items():
        if not Path(p).is_symlink() or os.readlink(p)!=target:raise ValueError('Link changed: '+p)
    for p,h in m['files'].items():
        if sha(p)!=h:raise ValueError('Bytes changed: '+p)


def check(packet,request,m):
    response=validate_packet(packet,request)
    if packet['upstream_sha256']!=m['files'][str(ROOT/'upstream/airis.py')]:raise ValueError('Upstream identity')
    r=packet['runtime'];files=m['files']
    if not r['executable_mappings'] or any(p not in files for p in r['executable_mappings']):raise ValueError('Unpinned map')
    if not r['imported_files'] or any(files.get(p)!=h for p,h in r['imported_files'].items()):raise ValueError('Unpinned import')
    if r['flags']!={'isolated':1,'no_site':1,'no_user_site':1,'dont_write_bytecode':1}:raise ValueError('Isolation flags')
    prefix=str(Path(m['python']).resolve().parent.parent)
    if r['prefix']!=prefix or r['base_prefix']!=prefix:raise ValueError('Python prefix')
    expected=[str(ROOT/'source'),prefix+'/lib/python312.zip',prefix+'/lib/python3.12',prefix+'/lib/python3.12/lib-dynload']
    if r['search_path']!=expected:raise ValueError('Import search path')
    return response


def logs(directory):
    records={}
    for p in directory.rglob('*'):
        if p.is_symlink():raise ValueError('Unexpected evidence symlink')
        if p.is_file() and p.parent.name in ('airis logs','training logs'):
            if p.suffix!='.log' or p.stat().st_size>256*1024:raise ValueError('Log file cap')
            records[str(p.relative_to(directory))]={'bytes':p.stat().st_size,'sha256':sha(p)}
    if not 1<=len(records)<=8 or sum(r['bytes'] for r in records.values())>512*1024:raise ValueError('Log aggregate cap')
    return records


def run(request,m,d):
    verify(m);d.mkdir(exist_ok=False);(d/'request.json').write_bytes(canonical(request))
    proc=None;streams=[];errors=[];failure=None;packet=None;result=None;log_proof=None;start=time.monotonic()
    try:
        streams.append((d/'stdout').open('xb'));streams.append((d/'stderr').open('xb'))
        cmd=[m['python'],'-I','-S','-B',str(REPO/'omega-baseline/scripts/no-network.py'),m['python'],
            '-I','-S','-B',str(ROOT/'source/launch.py'),str(os.getpid())]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=streams[0],stderr=streams[1],cwd=d,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},close_fds=True,start_new_session=True)
        proc.communicate(canonical(request),timeout=15)
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
    try:
        if failure is not None:raise failure
        if errors or proc is None or proc.returncode!=0:raise ValueError('Native process/finalization failed')
        if (d/'stderr').read_bytes()!=b'ROKO_AIRIS_OUTPUT_ROUTE_SENTINEL\n':raise ValueError('Diagnostic mismatch')
        packet=decode((d/'stdout').read_bytes(),49152);result=check(packet,request,m);log_proof=logs(d);verify(m)
    except BaseException as exc:failure=exc
    receipt=dict(status='passed' if failure is None else 'failed',seconds=time.monotonic()-start,
        returncode=None if proc is None else proc.returncode,error=None if failure is None else repr(failure),
        finalization_errors=errors,response=result,logs=log_proof,executed_external_actions=0)
    (d/'receipt.json').write_bytes(canonical(receipt)+b'\n')
    if failure is not None:raise failure
    return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--base-manifest',type=Path,required=True)
    p.add_argument('--python',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);m=prepare(json.loads(a.base_manifest.read_bytes()),a.python)
    (a.output/'manifest.json').write_bytes(canonical(m)+b'\n');start=time.monotonic();results=[];error=None
    try:
        for name,delta,query in CASES:results.append(run(fixture(name,delta,query),m,a.output/name))
        if results[0]['response']['predictions']!=results[3]['response']['predictions']:raise ValueError('Fresh reset disagreement')
    except BaseException as exc:error=repr(exc)
    result=dict(status='passed' if error is None and len(results)==4 else 'failed',cases=results,error=error,
        seconds=time.monotonic()-start,manifest_sha256=hashlib.sha256(canonical(m)).hexdigest(),
        full_airis=False,conversation_integrated=False,executed_external_actions=0)
    (a.output/'result.json').write_bytes(canonical(result)+b'\n')
    print(json.dumps({'status':result['status'],'seconds':result['seconds'],'cases':len(results),'error':error}))
    return int(result['status']!='passed')
if __name__=='__main__':raise SystemExit(main())
