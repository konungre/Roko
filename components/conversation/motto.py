"""Optional supervised MeTTa-Motto transport around the existing native provider."""
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time

from cognition import write_record
from learning import finalize_process

ROOT = Path(__file__).resolve().parents[1] / 'motto_conversation'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def validate_profile(profile):
    config = profile['motto_transport']
    if set(config) != {'python', 'guard_manifest', 'guard_admission', 'evidence_root'}:
        raise ValueError('Motto profile schema')
    if not all(Path(config[key]).is_absolute() for key in ('python', 'guard_manifest', 'evidence_root')):
        raise ValueError('Require absolute trusted Motto paths')
    pins = profile['files']
    if config['python'] not in pins or pins.get(config['guard_manifest']) != config['guard_admission']:
        raise ValueError('Unpinned Motto interpreter or guard')
    manifest = json.loads(Path(config['guard_manifest']).read_bytes())
    for path, digest in manifest['files'].items():
        if pins.get(path) != digest:
            raise ValueError('Motto runtime guard closure missing')
    for path in ROOT.rglob('*'):
        if path.is_file() and pins.get(str(path)) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Unpinned Motto source')


class MottoTransport:
    def __init__(self, provider):
        self.provider = provider
        self.native_chat = provider.chat
        self.config = provider.profile['motto_transport']
        self.receipts = []
        root = Path(self.config['evidence_root'])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root

    def chat(self, messages):
        import durable_api
        claim = durable_api.current
        if claim is None:
            raise ValueError('Motto requires an active durable v2 claim')
        binding = {key: claim[key] for key in ('session_id', 'request_id')}
        import conversation
        binding['revision'] = claim['revision']
        if binding['revision'] != len(conversation.session.history) // 2:
            raise ValueError('Motto claim/history revision mismatch')
        snapshot = {'binding': binding, 'messages': messages}
        digest = hashlib.sha256(canonical(snapshot)).hexdigest()
        directory = Path(tempfile.mkdtemp(prefix='motto-' + digest + '-', dir=self.root))
        write_record(directory / 'turn-start.json', snapshot)
        source = Path(__file__).resolve().parent
        stamp = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19]
        command = [self.provider.profile['python'], '-B', str(source / 'fresh_supervise.py'),
                   '--parent-pid', str(os.getpid()), '--parent-start', stamp, '--seconds', '210', '--',
                   self.config['python'], '-I', '-B', str(ROOT / 'worker.py'),
                   self.config['guard_manifest'], self.config['guard_admission']]
        proc = None
        out = err = b''
        failure = None
        request_raw = b''
        try:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True, bufsize=0,
                                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'})
            pending = memoryview(canonical({'messages': messages, 'snapshot_sha256': digest}) + b'\n')
            while pending:
                written = proc.stdin.write(pending)
                if not written:
                    raise BrokenPipeError('Incomplete Motto request write')
                pending = pending[written:]
            proc.stdin.flush()
            deadline = time.monotonic() + 20
            while not request_raw.endswith(b'\n'):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([proc.stdout], [], [], remaining)[0]:
                    raise TimeoutError('Motto request deadline')
                byte = os.read(proc.stdout.fileno(), 1)
                if not byte or len(request_raw) >= 65536:
                    raise ValueError('Motto incomplete or oversized request')
                request_raw += byte
            request = json.loads(request_raw)
            if request != {'stage': 'model_request', 'messages': messages, 'snapshot_sha256': digest}:
                raise ValueError('Motto changed model input or binding')
            text = self.native_chat(messages)
            out, err = proc.communicate(canonical({'text': text}) + b'\n', timeout=20)
            response = json.loads(out)
            if (proc.returncode or b'descendants_cleaned=1' not in err
                    or response != {'stage': 'completed', 'text': text, 'snapshot_sha256': digest}
                    or hashlib.sha256(canonical(snapshot)).hexdigest() != digest):
                raise ValueError('Motto response, snapshot or cleanup mismatch')
        except BaseException as error:
            failure = error
        out, err, failure, errors, fragments = finalize_process(proc, out, err, failure)
        receipt = {'binding': binding, 'snapshot_sha256': digest, 'executed_actions': 0,
                   'status': 'passed' if failure is None else 'failed',
                   'request_hex': request_raw.hex(), 'stdout_hex': out.hex(), 'stderr_hex': err.hex(),
                   'finalization_errors': errors, 'output_fragments': fragments,
                   'error': None if failure is None else repr(failure)}
        self.receipts.append(receipt)
        try:
            write_record(directory / 'receipt.json', receipt)
        except BaseException as error:
            errors.append({'stage': 'receipt-write', 'type': type(error).__name__, 'error': str(error)})
            failure = failure or error
            receipt.update(status='failed', error=repr(failure))
        if failure is not None:
            failure.receipt = receipt
            raise failure
        return text
