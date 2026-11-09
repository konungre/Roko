"""Finite process controller for pinned workers. Data-only results, no tools.

Native provenance here means an observed child in this process, not signed
attestation. Pure response validators alone never establish native execution.
"""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from paths import HERE, ROOT, MANIFEST, IMPORTS, SWI, PYTHON, SYSTEM
from contract import canonical, decode, parse_request, validate_response, response_from_native
from helper_probes import PROBES

WALL=20.0
STDOUT_CAP=49152
STDERR_CAP=16384
RSS_CAP=256*1024**2

def budget(deadline):
    if time.monotonic() >= deadline:raise TimeoutError("Outer budget exhausted")

def sha(p, deadline=float("inf")):
    budget(deadline)
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while b:=f.read(1024**2):
            budget(deadline);h.update(b)
    budget(deadline)
    return h.hexdigest()

def verify_inputs(admission, deadline=float("inf")):
    if type(admission) is not str or sha(MANIFEST,deadline)!=admission:
        raise ValueError('Exact reviewed manifest digest required')
    lock=json.loads(MANIFEST.read_bytes())
    for name,expected in lock['tree_entries'].items():
        budget(deadline)
        directory=Path(name)
        entries=sorted(directory.rglob('*'))
        if [str(p.relative_to(directory)) for p in entries]!=expected:raise ValueError('Native import tree membership changed: '+name)
        if any('__pycache__' in p.parts or p.suffix in ('.pyc','.pyo') for p in entries):raise ValueError('Python cache forbidden')
    for name,row in lock['files'].items():
        budget(deadline)
        p=Path(name)
        if p.resolve()!=p or not p.is_file() or p.stat().st_size!=row['bytes'] or (p.stat().st_mode & 0o7777)!=row['mode'] or sha(p,deadline)!=row['sha256']:
            raise ValueError('Pinned input changed: '+name)
    for name,target in lock['symlinks'].items():
        p=Path(name)
        if not p.is_symlink() or str(p.readlink())!=target:raise ValueError('Alias changed')
    budget(deadline)
    return lock

def available():
    values=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(values['MemAvailable'].split()[0])*1024

def validate_runtime(runtime,lock):
    if type(runtime) is not dict or set(runtime)!={'python','executable_mappings'} or canonical(runtime['python'])!=b'[3,12,14]':
        raise ValueError('Native ABI mismatch')
    paths=runtime['executable_mappings']
    required={str(SWI/'bin/x86_64-linux/swipl'),str(SWI/'lib/x86_64-linux/janus.so'),str(PYTHON/'lib/libpython3.12.so.1.0')}
    if type(paths) is not list or not 3<=len(paths)<=64 or any(type(p) is not str for p in paths) or len(set(paths))!=len(paths) or not required<=set(paths):
        raise ValueError('Native maps incomplete')
    for p in paths:
        if p not in lock['files'] or not lock['files'][p]['elf'] or not any(Path(p).is_relative_to(root) for root in (SWI,PYTHON,SYSTEM)):
            raise ValueError('Unexpected executable map')

def validate_completed(kind,raw,err,request,lock):
    if kind != 'metamo' or type(raw) is not bytes or not 1<=len(raw)<=32768 or type(err) is not bytes or len(err)>STDERR_CAP:
        raise ValueError('Native stream bounds')
    text=err.decode('utf-8',errors='strict')
    if 'ERROR:' in text or '\u274c' in text or text.splitlines().count('ROKO_METAMO_OUTPUT_ROUTE_SENTINEL')!=1:
        raise ValueError('Native diagnostics or output routing failure')
    packet=decode(raw,32768)
    keys={'version','request','response','strict_imports','native_selection_symbol','native_scores','native_delta','helper_probes','runtime','executed_actions'}
    if type(packet) is not dict or set(packet)!=keys or canonical(packet['version'])!=b'1' or canonical(packet['request'])!=canonical(request):
        raise ValueError('Native packet identity')
    if packet['strict_imports']!=[str(p) for p in IMPORTS] or canonical(packet['executed_actions'])!=b'0':
        raise ValueError('Native imports or authority')
    result=validate_response(canonical(packet['response']),request)
    expected=response_from_native(request,packet['native_scores'],packet['native_selection_symbol'],packet['native_delta'])
    if canonical(result)!=canonical(expected):raise ValueError('Native result substitution')
    probes=packet['helper_probes']
    if type(probes) is not list or len(probes)!=len(PROBES):raise ValueError('Missing compatibility probes')
    from bridge import near
    for observed,(name,expression,value) in zip(probes,PROBES):
        if type(observed) is not dict or set(observed)!={'name','observed'} or observed['name']!=name or not near(observed['observed'],value):
            raise ValueError('Helper probe mismatch')
    validate_runtime(packet['runtime'],lock)
    return result,packet['runtime']

def observed_exit(process):
    """Never reap here: retained child identity prevents PID/PGID reuse."""
    return os.waitid(os.P_PID,process.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)

def stop_owned(process, deadline):
    """Final group signal strictly precedes reap. Ownership loss never signals."""
    if process.returncode is not None:
        return {'returncode':process.returncode,'reaped':True,'signaled':False,'ownership':'already-reaped'}
    try:observed_exit(process)
    except ChildProcessError:
        return {'returncode':None,'reaped':False,'signaled':False,'ownership':'lost'}
    # No path between waitid and this final group signal reaps the owned leader.
    signaled=False
    try:
        os.killpg(process.pid,signal.SIGKILL);signaled=True
    except ProcessLookupError:pass
    remaining=min(2.0,max(0.001,deadline-time.monotonic()))
    try:
        code=process.wait(timeout=remaining)
        return {'returncode':code,'reaped':True,'signaled':signaled,'ownership':'owned-through-final-signal'}
    except subprocess.TimeoutExpired:
        return {'returncode':None,'reaped':False,'signaled':signaled,'ownership':'reap-timeout'}

def group_empty(pid):
    """Read-only procfs observation. No killpg(0) against a reaped group ID."""
    entries=list(Path('/proc').iterdir())
    if len(entries)>8192:raise ValueError('Procfs enumeration cap')
    for entry in entries:
        if not entry.name.isdecimal():continue
        try:
            with (entry/'stat').open('rb') as f:raw=f.read(4097)
        except (FileNotFoundError,ProcessLookupError):continue
        if not 1<=len(raw)<=4096:raise ValueError('Procfs stat cap')
        tail=raw.decode().rsplit(')',1)[1].split()
        if len(tail)<3:raise ValueError('Malformed procfs stat')
        if int(tail[2])==pid:return False
    return True

def replay_deferred_signal(saved, pending):
    """Deliver the first signal after bounded cleanup, never lose cancellation."""
    if not pending:return
    number=pending[0];handler=saved[number]
    if callable(handler):handler(number,None)
    elif handler!=signal.SIG_IGN:raise InterruptedError('Deferred native-stage signal '+str(number))

@contextmanager
def temporary_work(receipt_state):
    """Retain completed child evidence even if directory cleanup itself fails.

    An existing native/cancellation error remains the primary exception with its
    original class. Cleanup failure is additional evidence, never a pass.
    """
    primary=None
    try:
        with tempfile.TemporaryDirectory(prefix='native-',dir=ROOT) as work:
            try:
                yield work
            except BaseException as error:
                primary=error
                raise
    except BaseException as error:
        if primary is error:
            raise
        # Either creation/cleanup failed without a primary error, or __exit__
        # replaced an existing native/cancellation error. Attach any known receipt.
        receipt=receipt_state.get('receipt')
        if receipt is None and primary is not None:receipt=getattr(primary,'receipt',None)
        if receipt is not None:
            receipt.update(status='failed',temporary_cleanup='uncertain',
                temporary_cleanup_error=type(error).__name__+': '+str(error))
            if primary is not None:
                receipt['primary_error']=type(primary).__name__+': '+str(primary)
            else:
                receipt['error']=type(error).__name__+': '+str(error)
        target=primary if primary is not None else error
        if receipt is not None:target.receipt=receipt
        if primary is not None:
            raise primary from error
        raise


def run_native(kind,request,admission,*,outer_deadline):
    if kind!='metamo':raise ValueError('Only source-defined MetaMo worker')
    raw=canonical(request)
    request=parse_request(raw)
    lock=verify_inputs(admission,outer_deadline-3)
    launcher=Path(sys.executable).resolve(strict=True)
    if str(launcher)!=lock['host_launcher_python'] or str(launcher) not in lock['files']:
        raise ValueError('Actual host launcher differs from pinned interpreter')
    work_filesystem={'path':str(ROOT),'available_bytes':shutil.disk_usage(ROOT).free}
    if work_filesystem['available_bytes'] < 4*1024**3+8*1024**2:raise ValueError('4GiB reserve after 8MiB worst writes')
    if available()<4*1024**3:raise ValueError('4GiB available memory reserve')
    if time.monotonic()>=outer_deadline-3:raise TimeoutError('Outer deadline')
    started=time.monotonic(); deadline=min(started+WALL,outer_deadline-3)
    out=bytearray(); err=bytearray(); peak=0; minimum=available(); process=None; error=None; empty=False; cleanup=None
    receipt_state={}
    with temporary_work(receipt_state) as work:
        selector=selectors.DefaultSelector()
        try:
            process=subprocess.Popen([str(launcher),'-I','-B',str(HERE/'launch.py'),kind],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                cwd=work,env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8'},
                close_fds=True,start_new_session=True)
            streams={'stdin':process.stdin,'stdout':process.stdout,'stderr':process.stderr}
            for name,stream in streams.items():
                os.set_blocking(stream.fileno(),False)
                selector.register(stream,selectors.EVENT_WRITE if name=='stdin' else selectors.EVENT_READ,name)
            offset=0
            while selector.get_map():
                if time.monotonic()>deadline:raise TimeoutError('Native deadline')
                minimum=min(minimum,available())
                if minimum<4*1024**3:raise MemoryError('Host memory reserve')
                try:
                    status=Path(f'/proc/{process.pid}/status').read_text()
                    rss=next((int(x.split()[1])*1024 for x in status.splitlines() if x.startswith('VmRSS:')),0)
                    peak=max(peak,rss)
                    if peak>RSS_CAP:raise MemoryError('Worker RSS cap')
                except (FileNotFoundError,ProcessLookupError):pass
                for key,_ in selector.select(min(0.025,max(0,deadline-time.monotonic()))):
                    stream=key.fileobj; name=key.data
                    if name=='stdin':
                        try:offset+=os.write(stream.fileno(),raw[offset:])
                        except BrokenPipeError:raise ValueError('Worker closed request pipe')
                        if offset==len(raw):selector.unregister(stream);stream.close()
                    else:
                        chunk=os.read(stream.fileno(),4096)
                        if not chunk:selector.unregister(stream);stream.close();continue
                        target=out if name=='stdout' else err; cap=STDOUT_CAP if name=='stdout' else STDERR_CAP
                        room=max(0,cap-len(target));target.extend(chunk[:room])
                        if len(chunk)>room:raise ValueError('Native output cap')
            while observed_exit(process) is None:
                if time.monotonic()>=deadline:raise TimeoutError('Native post-pipe deadline')
                time.sleep(0.005)
        except BaseException as exc:error=exc
        finally:
            # Defer signals during bounded owned cleanup, then deliver the first.
            # Even a first cancellation arriving in this window must not be lost.
            saved={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM)}
            pending=[]
            def defer(number,frame):
                if not pending:pending.append(number)
            for sig in saved:signal.signal(sig,defer)
            try:
                if process is not None:
                    cleanup=stop_owned(process,min(outer_deadline-1,time.monotonic()+2))
                    if not cleanup['reaped']:error=RuntimeError('Worker ownership/reap failed: '+cleanup['ownership'])
                    empty=group_empty(process.pid)
                    if not empty:error=RuntimeError('Observed worker process group remains')
            except BaseException as cleanup_error:error=cleanup_error
            finally:
                try:selector.close()
                finally:
                    if process is not None:
                        for stream in (process.stdin,process.stdout,process.stderr):
                            if not stream.closed:stream.close()
                    for sig,handler in saved.items():signal.signal(sig,handler)
            try:replay_deferred_signal(saved,pending)
            except BaseException as deferred:error=deferred
        if error is None and process.returncode!=0:error=ValueError('Native worker returned '+str(process.returncode))
        receipt={'kind':kind,'launcher_python':str(launcher),'seconds':time.monotonic()-started,'returncode':None if process is None else process.returncode,
            'stdout':bytes(out).decode('utf-8',errors='replace'),'stderr':bytes(err).decode('utf-8',errors='replace'),
            'peak_rss_bytes':peak,'minimum_available_bytes':minimum,'group_empty':empty,'work_filesystem':work_filesystem,
            'manifest_sha256':admission,'authorizes_actions':False,'executed_actions':0,'cleanup':cleanup,'posthash_status':'not-completed'}
        receipt_state['receipt']=receipt
        if error is not None:
            receipt.update(status='failed',error=type(error).__name__+': '+str(error))
            if not isinstance(error, Exception):
                error.receipt=receipt;raise error
            exc=RuntimeError(receipt['error']);exc.receipt=receipt;raise exc
        try:
            result,runtime=validate_completed(kind,bytes(out),bytes(err),request,lock)
            verify_inputs(admission,outer_deadline-1)
            if list(Path(work).iterdir()):raise ValueError('Unexpected worker filesystem output')
            budget(outer_deadline-1)
        except BaseException as failure:
            receipt.update(status='failed',error=type(failure).__name__+': '+str(failure))
            if not isinstance(failure,Exception):
                failure.receipt=receipt;raise
            exc=RuntimeError(receipt['error']);exc.receipt=receipt;raise exc from failure
        receipt.update(status='passed',native_tested=True,runtime=runtime,inputs_unchanged=True,temporary_files=[],posthash_status='completed-unchanged')
        return result,receipt
