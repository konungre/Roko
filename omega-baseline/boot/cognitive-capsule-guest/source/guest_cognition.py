"""Controller-owned, opt-in bounded cognition. This module never imports Janus.

Admission is an audit gate for this trusted fixture, not a security sandbox.
The worker gets only one detached JSON request, not a StateStore handle.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

from cognition_protocol import (MAX_REQUEST, MAX_RESPONSE, MAX_STDERR, canonical,
                                decode, validate_request, validate_response)

CAPSULE_CAP = 128 * 1024**2
CHILD_RSS_CAP = 256 * 1024**2
GUEST_AVAILABLE_FLOOR = 512 * 1024**2
WALL_SECONDS = 30


class CognitiveError(ValueError):
    def __init__(self, reason, receipt=None):
        super().__init__(reason)
        self.receipt = receipt or {}


def request_for(state, revision, evidence_id, operation='arithmetic'):
    snapshot = state.snapshot()
    if snapshot['phase'] != 'open':
        raise ValueError('Cognition requires an open task')
    if type(evidence_id) is not str or evidence_id not in snapshot['evidence']:
        raise ValueError('Unknown evidence')
    evidence = dict(snapshot['evidence'][evidence_id], id=evidence_id)
    return validate_request({'version': 1, 'operation': operation,
                             'task_id': snapshot['task_id'], 'goal': snapshot['goal'],
                             'revision': revision, 'evidence': evidence})


def apply_response(state, current_revision, request, raw):
    # A changed goal/evidence/task/revision cannot reuse an earlier successful reply.
    current = request_for(state, current_revision, request['evidence']['id'], request['operation'])
    if canonical(current) != canonical(request):
        raise CognitiveError('Controller state changed while cognition was running')
    result = validate_response(raw, current)
    if request['operation'] == 'arithmetic':
        state.propose(state.task_id, 'record_answer', {'text': str(result['answer'])},
                      [request['evidence']['id']])
        check = state.verify_arithmetic()  # Existing, independent deterministic checker.
        if not check['accepted']:
            raise CognitiveError('MeTTa answer failed independent controller verification')
        if state.snapshot()['phase'] != 'verified' or check['authorizes_actions'] is not False:
            raise CognitiveError('Unexpected controller authority or phase')
    return result


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise CognitiveError('Nonregular capsule file: ' + str(path))
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise CognitiveError('Capsule file budget exceeded')
    return data


def inspect_capsule(root, admission):
    root = Path(root).resolve()
    raw = read_regular(root / 'manifest.json', 1024**2)
    manifest = decode(raw, 1024**2)
    permit = decode(read_regular(admission, 4096), 4096)
    expected = {'version': 1, 'scope': 'single-guest-cognitive-gate',
                'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'native_execution_reviewed': True}
    if canonical(permit) != canonical(expected):
        raise CognitiveError('This capsule has no matching reviewed execution admission')
    if manifest.get('version') != 1 or manifest.get('status') != 'prepared-not-native-tested':
        raise CognitiveError('Unexpected capsule manifest')
    total = 0
    files = manifest.get('files')
    if type(files) is not dict or not 1 <= len(files) <= 1400:
        raise CognitiveError('Invalid capsule file inventory')
    for name, pin in files.items():
        relative = Path(name)
        if relative.is_absolute() or not relative.parts or '..' in relative.parts:
            raise CognitiveError('Unsafe capsule path')
        path = root / relative
        if any(p.is_symlink() for p in [path, *list(path.parents)[:len(relative.parts)-1]]):
            raise CognitiveError('Symlink in capsule path')
        if type(pin) is not dict or set(pin) != {'sha256', 'bytes', 'mode'}:
            raise CognitiveError('Invalid capsule pin')
        if type(pin['bytes']) is not int or not 0 <= pin['bytes'] <= CAPSULE_CAP:
            raise CognitiveError('Invalid capsule file size')
        total += pin['bytes']
        if total > CAPSULE_CAP:
            raise CognitiveError('Capsule exceeds128MiB')
        data = read_regular(path, pin['bytes'])
        if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256'] or stat.S_IMODE(path.stat().st_mode) != pin['mode']:
            raise CognitiveError('Capsule integrity mismatch: ' + name)
    if total != manifest.get('payload_bytes'):
        raise CognitiveError('Capsule aggregate size mismatch')
    return manifest


def memory_sample(pid):
    status = Path('/proc/%d/status' % pid).read_text()
    rss = max([int(line.split()[1]) * 1024 for line in status.splitlines()
               if line.startswith(('VmRSS:', 'VmHWM:'))] or [0])
    available = None
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            available = int(line.split()[1]) * 1024
    if available is None:
        raise CognitiveError('Guest available-memory sample missing')
    return rss, available


class Budget:
    """Pure state machine, exercised with simulated clocks/output before native admission."""
    def __init__(self, started):
        self.started = started
        self.output = {'stdout': bytearray(), 'stderr': bytearray()}
        self.peak_rss_bytes = 0
        self.minimum_available_bytes = None

    def feed(self, stream, chunk):
        cap = {'stdout': MAX_RESPONSE, 'stderr': MAX_STDERR}[stream]
        remaining = cap - len(self.output[stream])
        self.output[stream].extend(chunk[:remaining])
        if len(chunk) > remaining:
            raise CognitiveError(stream + ' byte budget exceeded')

    def check(self, now, rss=0, available=GUEST_AVAILABLE_FLOOR, cancelled=False):
        self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
        self.minimum_available_bytes = available if self.minimum_available_bytes is None else min(self.minimum_available_bytes, available)
        if cancelled:
            raise CognitiveError('Cognitive worker cancelled')
        if now - self.started >= WALL_SECONDS:
            raise CognitiveError('Cognitive worker30s deadline exceeded')
        if rss > CHILD_RSS_CAP:
            raise CognitiveError('Cognitive worker256MiB RSS cap exceeded')
        if available < GUEST_AVAILABLE_FLOOR:
            raise CognitiveError('Guest512MiB available-memory floor crossed')

    def receipt(self):
        return {'stdout': bytes(self.output['stdout']).decode('utf-8', errors='replace'),
                'stderr': bytes(self.output['stderr']).decode('utf-8', errors='replace'),
                'peak_rss_bytes': self.peak_rss_bytes,
                'minimum_guest_available_bytes': self.minimum_available_bytes,
                'executed_actions': 0, 'authorizes_actions': False}



def validate_runtime_receipt(stderr, manifest):
    lines = stderr.decode('utf-8', errors='strict').splitlines()
    marker = 'ROKO_COGNITIVE_RUNTIME '
    records = [line[len(marker):] for line in lines if line.startswith(marker)]
    if len(records) != 1:
        raise CognitiveError('Missing or ambiguous native executable-map receipt')
    runtime = decode(records[0].encode('utf-8'), MAX_STDERR)
    if type(runtime) is not dict or set(runtime) != {'python', 'executable_mappings'} or canonical(runtime['python']) != b'[3,12,14]':
        raise CognitiveError('Unexpected embedded native runtime version')
    mappings = runtime['executable_mappings']
    if type(mappings) is not list or not 3 <= len(mappings) <= 64 or any(type(x) is not str for x in mappings):
        raise CognitiveError('Invalid native executable-map inventory')
    if len(set(mappings)) != len(mappings) or any(name not in manifest['elf_metadata'] for name in mappings):
        raise CognitiveError('Native mapping is outside manifest ELF closure')
    required = {'capsule/swipl/bin/x86_64-linux/swipl',
                'capsule/swipl/lib/x86_64-linux/janus.so',
                'capsule/python/lib/libpython3.12.so.1.0'}
    if not required <= set(mappings):
        raise CognitiveError('Missing actual SWI/Janus/Python3.12 mapping')
    return runtime


def run_request(request, root, admission, cancel=None):
    return _run_worker(validate_request(request), root, admission, cancel)


def run_primitive(root, admission, cancel=None):
    """The earlier0,1,0 fixture, first in the newly relocated capsule."""
    return _run_worker(None, root, admission, cancel, primitive=True)


def _run_worker(request, root, admission, cancel=None, primitive=False):
    root = Path(root).resolve()
    manifest = inspect_capsule(root, admission)
    # A permit alone cannot accidentally start the capsule in a host interpreter.
    if sys.version_info[:2] != (3, 13) or sys.executable != '/usr/bin/python3.13':
        raise CognitiveError('Native gate is restricted to the admitted guest Python3.13 controller')
    proc = None
    budget = Budget(time.monotonic())
    receipt = {'status': 'starting', 'native_tested': False}
    selector = selectors.DefaultSelector()
    with tempfile.TemporaryDirectory(prefix='roko-cognition-', dir='/tmp') as directory:
        try:
            budget.check(time.monotonic(), available=memory_sample(os.getpid())[1],
                         cancelled=cancel is not None and cancel.is_set())
            proc = subprocess.Popen([sys.executable, '-I', '-B', str(root / ('capsule/bridge/launch-smoke.py' if primitive else 'capsule/bridge/launch.py'))],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=directory, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                                    close_fds=True, start_new_session=True)
            pending = bytearray(b'' if primitive else canonical(request))
            for stream, event, label in ((proc.stdin, selectors.EVENT_WRITE, 'stdin'),
                                          (proc.stdout, selectors.EVENT_READ, 'stdout'),
                                          (proc.stderr, selectors.EVENT_READ, 'stderr')):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, label)
            while selector.get_map() or proc.poll() is None:
                try:
                    rss, available = memory_sample(proc.pid)
                except FileNotFoundError:
                    if proc.poll() is None:
                        raise
                    rss, available = 0, memory_sample(os.getpid())[1]
                budget.check(time.monotonic(), rss, available,
                             cancelled=cancel is not None and cancel.is_set())
                for key, _ in selector.select(.02):
                    if key.data == 'stdin':
                        try:
                            sent = os.write(key.fd, pending)
                        except BrokenPipeError:
                            sent = len(pending)
                        del pending[:sent]
                        if not pending:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        chunk = os.read(key.fd, 4096)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        else:
                            budget.feed(key.data, chunk)
            if proc.wait(timeout=1) != 0:
                raise CognitiveError('Native cognitive worker failed')
            if primitive:
                expected = [b'ROKO_GUEST_PETTA_ARITHMETIC_PASSED result=56',
                            b'ROKO_GUEST_JANUS_PASSED result=42',
                            b'ROKO_GUEST_OMEGA_MESSAGES_PASSED counts=0,1,0']
                if bytes(budget.output['stdout']).splitlines() != expected:
                    raise CognitiveError('Relocated primitive smoke markers differ')
                result = {'primitive_counts': [0, 1, 0], 'arithmetic': 56, 'janus_sum': 42,
                          'authorizes_actions': False, 'executed_actions': 0}
            else:
                result = validate_response(bytes(budget.output['stdout']), request)
            runtime = validate_runtime_receipt(bytes(budget.output['stderr']), manifest)
            receipt.update(runtime=runtime, status='native-response-validated', native_tested=True,
                           returncode=proc.returncode)
            return result, {**receipt, **budget.receipt()}
        except BaseException as error:
            receipt.update(status='failed', reason=type(error).__name__ + ': ' + str(error))
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise CognitiveError(str(error), {**receipt, **budget.receipt()}) from error
        finally:
            # Even a successful leader exit must not leave an in-group descendant.
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=2)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    stream.close()
            selector.close()


def run_and_verify(state, revision, evidence_id, root, admission, cancel=None):
    request = request_for(state, revision, evidence_id)
    result, receipt = run_request(request, root, admission, cancel)
    try:
        apply_response(state, revision, request, canonical(result))
    except ValueError as error:
        raise CognitiveError(str(error), receipt) from error
    return {'cognition': result, 'native_receipt': receipt,
            'check': state.snapshot()['verification'], 'executed_actions': 0}
