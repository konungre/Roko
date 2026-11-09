"""On-demand one-request candidate. No daemon, shell, network or actions.

Omega's actual provider registry, locked Granite and independent WorkingState
checks are reused. ECAN and MeTTa literal roundtrip are NOT part of this path.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import uuid

import live_contract as contract
from state_store import StateStore, RevisionConflict, CommitUncertain, canonical

INSTALL = Path('/opt/roko/desktop/live-request')
MODEL = Path('/run/roko-guest-cognition/model')
PERSISTENT = Path('/var/lib/roko/live-requests')
PROVIDER_ID = 'BasiliskLiveLocalGraniteV1'
WHOLE_SECONDS = 1200
NATIVE_COMPLETE = b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1'
RESULT_CAP = 65536


class Cancelled(BaseException):
    """Cancellation must escape the upstream registry's Exception handler."""



def write_receipt(path, raw, cap):
    if type(raw) is not bytes or len(raw) > cap:
        raise ValueError('Receipt byte cap')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def result_base(task_id=None):
    return {'version': 1, 'task_id': task_id, 'proposal': None, 'checked': None,
            'accepted': False, 'error': None, 'state_stale': False,
            'native_invoked': False, 'cancelled': False, 'executed_actions': 0, 'authorizes_actions': False,
            'live_subset': 'Omega provider registry / Granite / independent checker / CAS',
            'model_transport': 'readonly-regular-live-media-v1',
            'ecan_exercised': False, 'metta_roundtrip_exercised': False,
            'model_hash_unchanged': False, 'model_descriptor_closed': False,
            'reboot_persistence_tested': False}


def _run(request, task_id, store, output, *, provider, registry, renderer, recheck,
         arm=lambda _: None, clock=time.monotonic):
    """Pure-test seam; production chooses every dependency and path in run()."""
    request = contract.validate_request(request)
    started = clock()
    report = result_base(task_id)
    state = block = response = req = None
    revision = None
    failure = None
    try:
        state, revision = contract.create_state(store, task_id, request)
        req = contract.omega_request(registry, request['kind'], contract.message(state))
        rendered = renderer.render_prompt(req).encode('utf-8')
        write_receipt(output / 'request.json', canonical(request) + b'\n', contract.INPUT_CAP)
        write_receipt(output / 'prompt.txt', rendered, 16384)
        report['prompt_sha256'] = hashlib.sha256(rendered).hexdigest()
        report['initial_revision'] = revision
        contract.unchanged(store, state, revision)
        arm(120)
        registry.registerLLMProvider(PROVIDER_ID, provider)
        registry.llmProviderStart(PROVIDER_ID)
        block = getattr(provider, '_raw_model', None)
        if not provider.ready or block is None or type(block.fd) is not int or block.fd < 0:
            raise ValueError('Provider did not retain an admitted local model descriptor')
        report['model_before'] = json.loads(canonical(block.report))
        report['backend'] = provider.backend
        contract.unchanged(store, state, revision)
        arm(930)
        report['native_invoked'] = True
        response = registry.llmProviderChat(req)
        if type(provider.last.get('returncode')) is not int or provider.last['returncode'] != 0:
            raise ValueError('Model process did not finish successfully')
        if NATIVE_COMPLETE not in provider.stderr_bytes.splitlines():
            raise ValueError('Model supervisor cleanup evidence missing')
        proposal = contract.offered_proposal(registry, response, req, request['kind'])
        parsed = renderer.parse_tool(provider.stdout_bytes.decode('utf-8', errors='strict'), req)
        if len(parsed.calls) != 1 or parsed.calls[0].name != proposal['name'] or parsed.calls[0].arguments != proposal['arguments']:
            raise ValueError('Registry proposal differs from exact model output')
        report['proposal'] = proposal
    except BaseException as exc:
        failure = exc
    finally:
        # Exact bytes and hash/identity recheck precede all proposal/check writes.
        for name, cap in (('stdout', 32768), ('stderr', 1024 * 1024)):
            try:
                raw = getattr(provider, name + '_bytes')
                if type(raw) is not bytes:
                    raise ValueError('Exact model diagnostic bytes unavailable')
                write_receipt(output / ('model.' + name), raw[:cap], cap)
                report[name + '_sha256'] = hashlib.sha256(raw[:cap]).hexdigest()
                if len(raw) > cap or provider.last.get(name + '_truncated') is True:
                    raise ValueError('Model diagnostic stream exceeded bound')
            except BaseException as exc:
                failure = failure or exc
        block = block if block is not None else getattr(provider, '_raw_model', None)
        try:
            if isinstance(failure, Cancelled):
                raise failure  # Cancel promptly: no 4GB hash after cancellation.
            if block is None or block.fd is None:
                raise ValueError('Model descriptor unavailable for posthash')
            arm(120)
            after = recheck(block, clock() + 120)
            if canonical(report.get('model_before')) != canonical(after):
                raise ValueError('Model full hash/identity changed')
            report['model_hash_unchanged'] = True
        except BaseException as exc:
            failure = failure or exc
        finally:
            try:
                arm(20)
                provider.stop()
            except BaseException as exc:
                failure = failure or exc
            finally:
                if block is not None and block.fd is not None:
                    try:
                        block.close()
                    except BaseException as exc:
                        failure = failure or exc
                report['model_descriptor_closed'] = (not provider.ready
                    and getattr(provider, '_raw_model', None) is None
                    and (block is None or block.fd is None))
                if not report['model_descriptor_closed']:
                    failure = failure or ValueError('Model descriptor cleanup incomplete')
    if failure is None:
        try:
            arm(20)
            report.update(contract.save_and_check(store, state, revision, report['proposal'], request['kind']))
        except BaseException as exc:
            failure = exc
    if failure is not None:
        report['accepted'] = False
        report['error'] = type(failure).__name__ + ': ' + str(failure)[:1000]
        report['state_stale'] = isinstance(failure, (RevisionConflict, CommitUncertain))
        report['cancelled'] = isinstance(failure, Cancelled)
    report['seconds'] = round(clock() - started, 3)
    write_receipt(output / 'result.json', canonical(report) + b'\n', RESULT_CAP)
    return report


def private_directory(path, *, create=False):
    path = Path(path)
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022:
            raise ValueError('Unsafe persistent directory ancestry')
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise ValueError('Private owned 0700 state/receipt directory required')


def _production_modules():
    if Path(__file__).resolve() != INSTALL / 'live_controller.py' or sys.executable != '/usr/bin/python3.13' or sys.version_info[:2] != (3, 13):
        raise ValueError('Installed fixed guest endpoint and Python3.13 required')
    sys.path[:0] = [str(MODEL / 'adapters'), str(MODEL / 'vendor/PeTTa/repos/Omega/src'),
                    str(MODEL / 'vendor/guest-python')]
    import providers
    import granite_guest
    import media_transport
    import runtime_select
    import config
    import yaml
    expected = {providers: MODEL / 'vendor/PeTTa/repos/Omega/src/providers.py',
        granite_guest: MODEL / 'adapters/granite_guest.py', media_transport: MODEL / 'adapters/media_transport.py',
        runtime_select: MODEL / 'adapters/runtime_select.py', config: MODEL / 'vendor/PeTTa/repos/Omega/src/config.py',
        yaml: MODEL / 'vendor/guest-python/yaml/__init__.py'}
    for module, path in expected.items():
        if Path(module.__file__).resolve() != path:
            raise ValueError('Unexpected live provider module origin')
    return providers, granite_guest, media_transport


def run(request):
    request = contract.validate_request(request)
    registry, renderer, transport = _production_modules()
    private_directory(PERSISTENT)
    private_directory(PERSISTENT / 'state', create=True)
    private_directory(PERSISTENT / 'receipts', create=True)
    lock = os.open(PERSISTENT / 'request.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(lock).st_mode):
            raise ValueError('Live request lock must be regular')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Bound storage even if the user submits many sequential requests. No
        # deletion/eviction of old evidence; a full archive requires explicit care.
        if len(list((PERSISTENT / 'receipts').iterdir())) >= 64:
            raise ValueError('Live request archive has reached its 64-request limit')
        task_id = 'live-' + uuid.uuid4().hex
        output = PERSISTENT / 'receipts' / task_id
        output.mkdir(mode=0o700)
        provider = renderer.GraniteGuestProvider(MODEL, constrained=True)
        deadline = time.monotonic() + WHOLE_SECONDS
        old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
        def cancelled(signum, frame):
            raise Cancelled('Live request cancelled or bounded deadline expired')
        def arm(seconds):
            remaining = min(seconds, deadline - time.monotonic())
            if remaining <= 0:
                raise TimeoutError('Whole live request deadline expired')
            signal.setitimer(signal.ITIMER_REAL, remaining)
        for sig in old_handlers:
            signal.signal(sig, cancelled)
        try:
            return _run(request, task_id, StateStore(PERSISTENT / 'state'), output,
                provider=provider, registry=registry, renderer=renderer,
                recheck=transport.recheck_model, arm=arm)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
    finally:
        os.close(lock)
