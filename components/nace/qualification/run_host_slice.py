"""Explicit host-slice gate, not the historical relocated-runtime admission.

Prepare never imports NACE. Run starts twelve fixed native_worker processes,
under OS resource limits, and compares actual output with a separate oracle.
Neither mode imports the full NACE application or performs world actions.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source'
sys.path.insert(0,str(SOURCE))
from fixtures import cases
from adapter import transition
from reference import ReferenceCore


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path,value):
    with path.open('xb') as stream:stream.write(encode(value)+b'\n')


def frozen_files():
    paths=sorted(SOURCE.glob('*.py'))+[Path(__file__).resolve(),
        ROOT/'proof/slice-lineage.json',ROOT/'proof/upstream-lock.json',
        Path(sys.executable).resolve(),Path(shutil.which('prlimit')).resolve()]
    return {str(p):digest(p.read_bytes()) for p in paths}


def prepare(directory):
    directory.mkdir(parents=True,exist_ok=False)
    lineage=json.loads((ROOT/'proof/slice-lineage.json').read_bytes())
    if digest((SOURCE/'nace_slice.py').read_bytes())!=lineage['slice_sha256']:
        raise ValueError('Derived slice differs from preserved upstream lineage')
    rows=cases()
    for row in rows:row['expected']=transition(row['request'],ReferenceCore())
    manifest={'schema':'roko.nace.host-slice-gate.v1','files':frozen_files(),
        'python':str(Path(sys.executable).resolve()),
        'prlimit':str(Path(shutil.which('prlimit')).resolve()),
        'cases':rows,'limits':{'cpu_seconds':2,'address_space_bytes':268435456,
            'file_bytes':32768,'open_files':64,'processes':1,'core_bytes':0,
            'case_wall_seconds':5,'gate_wall_seconds':45},
        'scope':'twelve fixed synthetic 3x3 predictions; seven actual upstream functions',
        'runtime_scope':'host Python binary and prlimit pinned; standard-library and shared-library closure not frozen',
        'sandbox_scope':'resource limits only; not a general filesystem or network sandbox',
        'executed_actions':0,'native_executed':False}
    write_new(directory/'manifest.json',manifest)
    return digest((directory/'manifest.json').read_bytes())


def equivalent(observed,expected):
    if type(observed) is not type(expected):return False
    if isinstance(expected,dict):
        return observed.keys()==expected.keys() and all(equivalent(observed[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return len(observed)==len(expected) and all(equivalent(a,b) for a,b in zip(observed,expected))
    if type(expected) is float:
        return math.isfinite(observed) and math.isclose(observed,expected,rel_tol=1e-12,abs_tol=1e-12)
    return observed==expected


def run_case(row,manifest,directory,deadline):
    start=time.monotonic();proc=None;streams=[];errors=[];result=None
    stdout=directory/(row['id']+'.stdout');stderr=directory/(row['id']+'.stderr')
    limits=manifest['limits']
    command=[manifest['prlimit'],'--cpu=2:2','--as=268435456:268435456',
        '--fsize=32768:32768','--nofile=64:64','--nproc=1:1','--core=0:0','--',
        manifest['python'],'-I','-B',str(SOURCE/'native_worker.py')]
    try:
        streams=[stdout.open('xb')]
        streams.append(stderr.open('xb'))
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=streams[0],stderr=streams[1],
            cwd=directory,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},
            start_new_session=True,close_fds=True)
        proc.communicate(encode(row['request']),timeout=max(.001,min(limits['case_wall_seconds'],deadline-time.monotonic())))
    except BaseException as exc:
        errors.append({'stage':'execution','error':type(exc).__name__+': '+str(exc)})
        if not isinstance(exc,Exception):result=exc
    finally:
        if proc is not None and proc.returncode is None:
            try:
                # No reap has occurred on the timeout path; leader identity is retained.
                os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as exc:errors.append({'stage':'kill','error':repr(exc)})
            try:proc.wait(timeout=2)
            except BaseException as exc:errors.append({'stage':'reap','error':repr(exc)})
        if proc is not None and proc.stdin is not None:
            streams.append(proc.stdin)
        for stream in streams:
            try:stream.close()
            except BaseException as exc:errors.append({'stage':'close','error':repr(exc)})
    raw=stdout.read_bytes() if stdout.exists() else b''
    err=stderr.read_bytes() if stderr.exists() else b''
    receipt={'case':row['id'],'seconds':time.monotonic()-start,
        'returncode':None if proc is None else proc.returncode,
        'stdout_sha256':digest(raw),'stderr_sha256':digest(err),
        'stdout_bytes':len(raw),'stderr_bytes':len(err),'errors':errors,
        'executed_actions':0,'status':'failed'}
    try:
        if errors or proc is None or proc.returncode!=0 or err or not 0<len(raw)<=16385:
            raise ValueError('Incomplete process or invalid output bounds')
        def constant(value):raise ValueError('Non-finite result')
        def pairs(items):
            out={}
            for key,value in items:
                if key in out:raise ValueError('Duplicate result key')
                out[key]=value
            return out
        observed=json.loads(raw,parse_constant=constant,object_pairs_hook=pairs)
        if observed.pop('worker_kind',None)!='actual_pinned_nace_function_slice':
            raise ValueError('Wrong worker provenance')
        if not equivalent(observed,row['expected']):raise ValueError('Native/oracle mismatch')
        receipt.update(status='passed',observed=observed)
    except Exception as exc:receipt['comparison_error']=str(exc)
    write_new(directory/(row['id']+'.receipt.json'),receipt)
    if result is not None:
        result.receipt=receipt
        raise result
    return receipt


def run(directory,admission):
    raw=(directory/'manifest.json').read_bytes()
    if digest(raw)!=admission:raise ValueError('Exact prepared manifest digest required')
    manifest=json.loads(raw)
    # Reconstruct the fixed schema/policy; manifest fields cannot widen the gate.
    if manifest['files']!=frozen_files():raise ValueError('Pinned source/runtime files changed')
    if manifest['python']!=str(Path(sys.executable).resolve()):raise ValueError('Wrong host Python')
    if manifest['prlimit']!=str(Path(shutil.which('prlimit')).resolve()):raise ValueError('Wrong prlimit')
    expected_rows=cases()
    for row in expected_rows:row['expected']=transition(row['request'],ReferenceCore())
    if manifest['cases']!=expected_rows:raise ValueError('Fixed cases changed')
    if manifest['limits']!={'cpu_seconds':2,'address_space_bytes':268435456,'file_bytes':32768,
        'open_files':64,'processes':1,'core_bytes':0,'case_wall_seconds':5,'gate_wall_seconds':45}:
        raise ValueError('Limits changed')
    # An output directory marks an attempted run permanently, including failures.
    output=directory/'observed';output.mkdir(exist_ok=False)
    started=time.monotonic();receipts=[];failure=None
    try:
        for row in manifest['cases']:
            if time.monotonic()-started>=45:raise TimeoutError('Whole gate deadline')
            receipt=run_case(row,manifest,output,started+45);receipts.append(receipt)
            if receipt['status']!='passed':raise ValueError('Stop after first failed native case')
    except BaseException as exc:
        failure=exc
        if getattr(exc,'receipt',None) is not None:receipts.append(exc.receipt)
    unchanged=manifest['files']==frozen_files()
    summary={'schema':'roko.nace.host-slice-result.v1','manifest_sha256':admission,
        'seconds':time.monotonic()-started,'cases':receipts,'inputs_unchanged':unchanged,
        'status':'passed' if failure is None and unchanged and len(receipts)==12 else 'failed',
        'scope':manifest['scope'],'runtime_scope':manifest['runtime_scope'],
        'sandbox_scope':manifest['sandbox_scope'],'conversation_integrated':False,
        'full_nace':False,'executed_actions':0}
    if failure is not None:summary['error']=type(failure).__name__+': '+str(failure)
    write_new(output/'result.json',summary)
    if failure is not None:raise failure
    if summary['status']!='passed':raise ValueError('Source changed after execution')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['prepare','run'])
    parser.add_argument('directory',type=Path)
    parser.add_argument('--admission')
    args=parser.parse_args()
    directory=args.directory.resolve()
    if args.mode=='prepare':print(prepare(directory))
    else:
        outcome=run(directory,args.admission)
        print(json.dumps({'status':outcome['status'],'cases':len(outcome['cases']),
            'seconds':outcome['seconds'],'inputs_unchanged':outcome['inputs_unchanged']}))
