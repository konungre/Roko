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
from paths import HERE, ROOT, MANIFEST, PYTHON, SYSTEM, PYTHON_BINARY
from contract import canonical, decode, parse_request, validate_packet, MAX_RESPONSE
from runtime_guard import validate_import_proof

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
    if type(runtime) is not dict or set(runtime)!={'python','executable_mappings','imports'} or canonical(runtime['python'])!=b'[3,12,14]':
        raise ValueError('Native ABI mismatch')
    validate_import_proof(runtime['imports'],lock)
    paths=runtime['executable_mappings']
    required={str(PYTHON_BINARY)}
    if type(paths) is not list or not 2<=len(paths)<=64 or any(type(p) is not str for p in paths) or len(set(paths))!=len(paths) or not required<=set(paths):
        raise ValueError('Native maps incomplete')
    for p in paths:
        if p not in lock['files'] or not lock['files'][p]['elf'] or not any(Path(p).is_relative_to(root) for root in (PYTHON,SYSTEM)):
            raise ValueError('Unexpected executable map')

def validate_completed(kind,raw,err,request,lock):
    if kind != 'airis':raise ValueError('Only AIRIS transition worker')
    if type(raw) is not bytes or not 1<=len(raw)<=STDOUT_CAP or type(err) is not bytes or len(err)>STDERR_CAP:
        raise ValueError('Native stream bounds')
    # No warning/error text is silently accepted for this minimal worker.
    if err != b'ROKO_AIRIS_OUTPUT_ROUTE_SENTINEL\n':raise ValueError('Unexpected native diagnostic output')
    packet=decode(raw,MAX_RESPONSE)
    result=validate_packet(packet,request)
    if packet['upstream_sha256']!=lock['files'][str(ROOT/'upstream/airis.py')]['sha256']:raise ValueError('Wrong AIRIS module')
    runtime=packet['runtime']
    validate_runtime(runtime,lock)
    return result,runtime


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


def finalize_native(process, selector, outer_deadline, primary):
    """Best-effort bounded finalization; return evidence instead of escaping.

    Every stage is attempted independently. Preserve the first primary failure,
    except that cancellation takes precedence over an ordinary exception.
    This function does not certify cleanup when any stage fails.
    """
    failures=[]; saved={}; pending=[]; cleanup=None; empty=False
    error=primary
    def record(stage, exc):
        nonlocal error
        failures.append({'stage':stage,'error':type(exc).__name__+': '+str(exc)})
        if error is None or (isinstance(error, Exception) and
                             (not isinstance(exc, Exception) or stage=='deferred-signal')):
            error=exc
    def defer(number, frame):
        if not pending:pending.append(number)
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM):
        try:
            saved[sig]=signal.getsignal(sig)
            signal.signal(sig,defer)
        except BaseException as exc:record('signal-defer:'+str(sig),exc)
    try:
        if process is not None:
            try:
                cleanup=stop_owned(process,min(outer_deadline-1,time.monotonic()+2))
                if not cleanup['reaped']:
                    raise RuntimeError('Worker ownership/reap failed: '+cleanup['ownership'])
            except BaseException as exc:record('owned-child',exc)
            try:
                empty=group_empty(process.pid)
                if not empty:raise RuntimeError('Observed worker process group remains')
            except BaseException as exc:record('process-group',exc)
        try:selector.close()
        except BaseException as exc:record('selector-close',exc)
        if process is not None:
            for name in ('stdin','stdout','stderr'):
                try:
                    stream=getattr(process,name)
                    if stream is not None and not stream.closed:stream.close()
                except BaseException as exc:record('stream-close:'+name,exc)
    finally:
        for sig,handler in saved.items():
            try:signal.signal(sig,handler)
            except BaseException as exc:record('signal-restore:'+str(sig),exc)
    try:replay_deferred_signal(saved,pending)
    except BaseException as exc:record('deferred-signal',exc)
    return error,cleanup,empty,failures


def run_native(kind,request,admission,*,outer_deadline):
    if kind!='airis':raise ValueError('Only fixed AIRIS transition worker')
    raw=canonical(request)
    request=parse_request(raw)
    lock=verify_inputs(admission,outer_deadline-3)
    launcher=Path(sys.executable).resolve(strict=True)
    if str(launcher)!=lock['host_launcher_python'] or str(launcher) not in lock['files']:
        raise ValueError('Actual host launcher differs from pinned interpreter')
    work_filesystem={'disk_free_bytes':shutil.disk_usage(ROOT).free}
    if work_filesystem['disk_free_bytes']<4*1024**3:raise ValueError('4GiB disk reserve')
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
            execution_error=error
            error,cleanup,empty,finalization_errors=finalize_native(process,selector,outer_deadline,error)
        if error is None and process.returncode!=0:error=ValueError('Native worker returned '+str(process.returncode))
        receipt={'kind':kind,'launcher_python':str(launcher),'seconds':time.monotonic()-started,'returncode':None if process is None else process.returncode,
            'stdout':bytes(out).decode('utf-8',errors='replace'),'stderr':bytes(err).decode('utf-8',errors='replace'),
            'peak_rss_bytes':peak,'minimum_available_bytes':minimum,'group_empty':empty,'work_filesystem':work_filesystem,
            'manifest_sha256':admission,'authorizes_actions':False,'executed_actions':0,'cleanup':cleanup,'posthash_status':'not-completed'}
        receipt['finalization_errors']=finalization_errors
        if execution_error is not None:
            receipt['execution_error']=type(execution_error).__name__+': '+str(execution_error)
        receipt_state['receipt']=receipt
        try:receipt['temporary_files']=audit_work_files(work)
        except BaseException as output_error:
            receipt['temporary_files']=getattr(output_error,'evidence',[])
            receipt['temporary_output_error']=type(output_error).__name__+': '+str(output_error)
            if error is None:error=output_error
        if error is not None:
            receipt.update(status='failed',error=type(error).__name__+': '+str(error))
            if not isinstance(error, Exception):
                error.receipt=receipt;raise error
            exc=RuntimeError(receipt['error']);exc.receipt=receipt;raise exc
        try:
            result,runtime=validate_completed(kind,bytes(out),bytes(err),request,lock)
            verify_inputs(admission,outer_deadline-1)
            outputs=audit_work_files(work)
            budget(outer_deadline-1)
        except BaseException as failure:
            receipt.update(status='failed',error=type(failure).__name__+': '+str(failure))
            if not isinstance(failure,Exception):
                failure.receipt=receipt;raise
            exc=RuntimeError(receipt['error']);exc.receipt=receipt;raise exc from failure
        receipt.update(status='passed',native_tested=True,runtime=runtime,inputs_unchanged=True,temporary_files=outputs,posthash_status='completed-unchanged')
        return result,receipt


class WorkOutputError(ValueError):
    def __init__(self,issues,evidence):
        super().__init__('; '.join(issues));self.evidence=evidence

def audit_work_files(work):
    import re
    import itertools
    import stat
    root=Path(work);rows=[];issues=[];counts={'airis logs':0,'training logs':0}
    expected={'airis logs':'airis init ', 'training logs':'training log '}
    top=list(itertools.islice(root.iterdir(),9))
    if len(top)>8:issues.append('Top-level output entry cap')
    if {p.name for p in top}!=set(expected):issues.append('Only two original log dirs allowed')
    for directory in top:
        if directory.name not in expected:issues.append('Unexpected output directory/file');continue
        if directory.is_symlink() or not directory.is_dir():issues.append('Original log directory must be a real directory');continue
        entries=list(itertools.islice(directory.iterdir(),9))
        if len(entries)>8:issues.append('Log directory entry cap')
        for p in entries:
            rel=p.relative_to(root)
            if re.fullmatch(re.escape(expected[directory.name])+r'\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.log',p.name) is None:
                issues.append('Unexpected output filename');continue
            if p.is_symlink() or not p.is_file():issues.append('Log must be a regular non-symlink file');continue
            counts[directory.name]+=1
            row={'path':str(rel)}
            try:
                fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                try:
                    before=os.fstat(fd);size=before.st_size;row['bytes']=size
                    if not stat.S_ISREG(before.st_mode):raise ValueError('Special log output')
                    if size>262144:raise ValueError('Log byte cap')
                    data=os.read(fd,262145)
                    after=os.fstat(fd)
                    if len(data)!=size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('Log changed during audit')
                    row.update(sha256=hashlib.sha256(data).hexdigest(),tail_utf8=data[-4096:].decode('utf-8',errors='replace'))
                finally:os.close(fd)
            except (OSError,ValueError) as e:
                row['evidence_error']=type(e).__name__+': '+str(e);issues.append('Recognized log evidence incomplete')
            rows.append(row)
    if counts!={'airis logs':1,'training logs':1}:issues.append('Exactly one original log per directory required')
    rows=sorted(rows,key=lambda x:x['path'])
    if issues:raise WorkOutputError(issues,rows)
    return rows
