"""Fixed host Hyperon runner with a locally prepared, hash-bound closure.

Runtime paths are trusted controller configuration. The request is data only.
Per-call evidence directories are immutable and intentionally retained.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sysconfig
import time
if __package__:
    from .contract import canonical,decode,validate_request,response_from_rows
else:
    from contract import canonical,decode,validate_request,response_from_rows

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
LIMITS=['--cpu=3:3','--as=536870912:536870912','--fsize=65536:65536',
        '--nofile=64:64','--nproc=1:1','--core=0:0']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def tree(root,exclude_site=False):
    root=Path(root);paths=[]
    for parent,dirs,files in os.walk(root,followlinks=False):
        if exclude_site and Path(parent)==root:dirs[:]=[d for d in dirs if d!='site-packages']
        for name in sorted(dirs+files):paths.append(str((Path(parent)/name).relative_to(root)))
    return sorted(paths)


def prepare(python,probe):
    python=Path(python).absolute();venv=python.parent.parent
    if not (venv/'pyvenv.cfg').is_file():raise ValueError('Dedicated venv required')
    maps=json.loads(Path(probe).read_bytes())
    if maps['hyperon_version']!='0.2.10':raise ValueError('Wrong Hyperon probe')
    roots={str(HERE):False,str(ROOT/'upstream'):False,str(venv):False,
           sysconfig.get_path('stdlib'):True}
    trees={p:tree(p,skip) for p,skip in roots.items()}
    files={};links={}
    paths=[Path('/usr/bin/prlimit'),python,Path(probe),*[Path(p) for p in maps['runtime_maps']]]
    for root,entries in trees.items():paths.extend(Path(root)/entry for entry in entries)
    for p in paths:
        if p.is_symlink():links[str(p)]=os.readlink(p)
        if p.is_file():files[str(p.resolve())]=sha(p)
    return {'schema':'roko.nars.hyperon-runtime.v1','python':str(python),'prlimit':'/usr/bin/prlimit',
        'roots':roots,'trees':trees,'files':files,'symlinks':links,
        'runtime_maps':maps['runtime_maps'],'limits':LIMITS,'worker':str(HERE/'worker.py'),
        'scope':'NAL-1 chain only; resource limits are not a general sandbox'}


def verify(manifest,admission):
    if hashlib.sha256(canonical(manifest)).hexdigest()!=admission:raise ValueError('Runtime admission digest')
    if manifest['schema']!='roko.nars.hyperon-runtime.v1' or manifest['limits']!=LIMITS:
        raise ValueError('Runtime schema/limits')
    if manifest['worker']!=str(HERE/'worker.py'):raise ValueError('Fixed worker required')
    for root,skip in manifest['roots'].items():
        if tree(root,skip)!=manifest['trees'][root]:raise ValueError('Closure membership changed')
    for name,target in manifest['symlinks'].items():
        if not Path(name).is_symlink() or os.readlink(name)!=target:raise ValueError('Closure symlink changed')
    for name,expected in manifest['files'].items():
        if not Path(name).is_file() or sha(name)!=expected:raise ValueError('Closure bytes changed: '+name)
    for name in (manifest['python'],manifest['prlimit'],manifest['worker']):
        if str(Path(name).resolve()) not in manifest['files']:raise ValueError('Unpinned executable/source')


def run_native(request,*,manifest,admission,evidence_directory):
    request=validate_request(request)
    verify(manifest,admission)
    directory=Path(evidence_directory);directory.mkdir(parents=True,exist_ok=False)
    output=directory/'stdout';diagnostic=directory/'stderr'
    start=time.monotonic();proc=None;streams=[];failure=None;errors=[]
    try:
        streams.append(output.open('xb'));streams.append(diagnostic.open('xb'))
        command=[manifest['prlimit'],*LIMITS,'--',manifest['python'],'-I','-B',manifest['worker'],
                 '--parent-pid',str(os.getpid())]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=streams[0],stderr=streams[1],
            cwd=directory,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},
            close_fds=True,start_new_session=True)
        proc.communicate(canonical(request),timeout=6)
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
    raw=output.read_bytes() if output.exists() else b''
    err=diagnostic.read_bytes() if diagnostic.exists() else b''
    receipt={'schema':'roko.nars.hyperon-receipt.v1','status':'failed',
        'manifest_sha256':admission,'request_sha256':hashlib.sha256(canonical(request)).hexdigest(),
        'returncode':None if proc is None else proc.returncode,'seconds':time.monotonic()-start,
        'stdout':raw.decode('utf-8',errors='replace'),'stderr':err.decode('utf-8',errors='replace'),
        'finalization_errors':errors,'executed_actions':0,'authorizes_actions':False}
    response=None
    try:
        if failure is not None:raise failure
        if errors or proc is None or proc.returncode!=0 or err:raise ValueError('Native process/finalization failed')
        packet=decode(raw,16385)
        if set(packet)!={'schema','request','native_rows','response','upstream_commit','hyperon_version',
                         'strict_imports','runtime_maps','executed_actions','full_nars','parent_lifetime_bound'}:
            raise ValueError('Native packet schema')
        if packet['schema']!='roko.nars.hyperon-observation.v1' or canonical(packet['request'])!=canonical(request):
            raise ValueError('Native request identity')
        if packet['upstream_commit']!='945e2f83711b143e3f6e2eb112cc40c4f531c6f2' or packet['hyperon_version']!='0.2.10':
            raise ValueError('Native component identity')
        if packet['strict_imports']!=['truthfunctions.metta','nal1.metta'] or packet['full_nars'] is not False:
            raise ValueError('Native scope')
        if type(packet['executed_actions']) is not int or packet['executed_actions']!=0:raise ValueError('Native authority')
        if packet['parent_lifetime_bound'] is not True:raise ValueError('Native parent lifetime not bound')
        if packet['runtime_maps']!=manifest['runtime_maps']:raise ValueError('Native executable maps changed')
        response=response_from_rows(request,packet['native_rows'])
        if canonical(response)!=canonical(packet['response']):raise ValueError('Native response substitution')
        verify(manifest,admission)
        receipt.update(status='passed',inputs_unchanged=True,runtime_maps=packet['runtime_maps'],
            response_sha256=hashlib.sha256(canonical(response)).hexdigest())
    except BaseException as exc:
        failure=exc;receipt['error']=type(exc).__name__+': '+str(exc)
    with (directory/'receipt.json').open('xb') as stream:stream.write(canonical(receipt)+b'\n')
    if failure is not None:
        failure.receipt=receipt
        raise failure
    return response,receipt
