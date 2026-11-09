"""Fresh-build host profile, separate from the immutable recovered-host receipt.

Uses real Omega provider dispatch. No action executor or remote fallback exists.
Symbolic context requires a separately qualified native ECAN profile.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import conversation
import recovered


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_profile(path):
    profile = json.loads(Path(path).read_text())
    if profile.get('kind') != 'roko-fresh-host-v1':
        raise ValueError('Require explicit fresh-build profile')
    for name, expected in profile['files'].items():
        if not Path(name).is_absolute() or digest(name) != expected:
            raise ValueError('Fresh closure mismatch: ' + name)
    for key in ('model', 'infer', 'swipl', 'python'):
        if profile[key] not in profile['files']:
            raise ValueError('Unpinned executable or model: ' + key)
    if profile['files'][profile['model']] != recovered.MODEL_SHA:
        raise ValueError('Unexpected Granite model identity')
    if 'nars_cognition' in profile:
        config=profile['nars_cognition']
        if type(config) is not dict or set(config)!={'manifest','admission','evidence_root'}:
            raise ValueError('NARS cognition configuration schema')
        if config['manifest'] not in profile['files'] or profile['files'][config['manifest']]!=config['admission']:
            raise ValueError('NARS manifest must be pinned in fresh closure')
        if not Path(config['evidence_root']).is_absolute():raise ValueError('Absolute NARS evidence root required')
    if 'mork_memory' in profile:
        config = profile['mork_memory']
        if type(config) is not dict or set(config) != {'manifest','manifest_sha256'}:
            raise ValueError('MORK configuration schema')
        if profile['files'].get(config['manifest']) != config['manifest_sha256']:
            raise ValueError('MORK manifest must be pinned in fresh closure')
    return profile


def no_context(candidates, **kwargs):
    raise ValueError('Native ECAN is not qualified in this fresh profile; use empty context')


class GenerationError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def generation_metadata(stderr, max_tokens):
    try:
        rows = [json.loads(x.split(' ', 1)[1]) for x in stderr.splitlines()
                if x.startswith('ROKO_GENERATION ')]
    except ValueError as error:
        raise GenerationError('invalid_generation_receipt') from error
    if len(rows) != 1:
        raise GenerationError('missing_generation_receipt')
    row = rows[0]
    if (type(row) is not dict or set(row) != {'input_tokens','output_tokens','finish_reason'}
            or type(row['input_tokens']) is not int or type(row['output_tokens']) is not int
            or not 0 <= row['output_tokens'] <= max_tokens
            or row['finish_reason'] not in ('eos','length','input_limit')):
        raise GenerationError('invalid_generation_receipt')
    if row['finish_reason'] == 'input_limit':
        raise GenerationError('context_limit')
    if not 1 <= row['input_tokens'] <= 512:
        raise GenerationError('invalid_generation_receipt')
    return row


class FreshProvider:
    def __init__(self, profile):
        try:
            probe = socket.socket()
        except PermissionError:
            pass
        else:
            probe.close()
            raise ValueError('Require inherited child-only network denial')
        self.profile = profile
        self.receipts = []
        self.ecan_receipts = []
        self.mork_receipts = []
        self.max_tokens = 64
        self.allow_partial = False
        self.last_generation = None
        self.last_error = None
        self.fd = os.open(profile['model'], os.O_RDONLY | os.O_NOFOLLOW)
        self.identity = os.fstat(self.fd)
        try:
            self.verify_model()
        except BaseException:
            self.close()
            raise

    def verify_model(self):
        digest = hashlib.sha256()
        offset = 0
        while block := os.pread(self.fd, 4 * 1024**2, offset):
            digest.update(block)
            offset += len(block)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
        if offset != 4230976352 or digest.hexdigest() != recovered.MODEL_SHA or identity(os.fstat(self.fd)) != identity(self.identity):
            raise ValueError('Model bytes or identity changed')

    def chat(self, messages):
        self.last_generation = None
        self.last_error = None
        prompt = recovered.render(messages)
        source = Path(__file__).resolve().parent
        parent_start = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19]
        command = [self.profile['python'], '-B', str(source/'fresh_supervise.py'),
                   '--parent-pid', str(os.getpid()), '--parent-start', parent_start,
                   '--seconds', '150', '--', self.profile['infer'],
                   '--model', f'/proc/{os.getpid()}/fd/{self.fd}', '--max-tokens', str(self.max_tokens)]
        started = time.monotonic()
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True,
                                env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8',
                                     'OMP_NUM_THREADS':'4', 'PYTHONDONTWRITEBYTECODE':'1'})
        print('ROKO_NATIVE_STARTED '+json.dumps({'supervisor_pid':proc.pid}), file=sys.stderr, flush=True)
        try:
            out, err = proc.communicate(prompt.encode(), timeout=165)
        except BaseException:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise
        receipt = {'returncode':proc.returncode, 'seconds':round(time.monotonic()-started,3),
                   'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                   'stdout':out.decode('utf-8'), 'stderr':err.decode('utf-8',errors='replace'),
                   'network_denied':True, 'executed_actions':0}
        self.receipts.append(receipt)
        try:
            generation = generation_metadata(receipt['stderr'], self.max_tokens)
        except GenerationError as error:
            self.last_error = error.code
            raise
        if proc.returncode or len(out)>32768 or len(err)>1024**2 or b'descendants_cleaned=1' not in err:
            raise RuntimeError('Fresh native inference failed: '+str(proc.returncode))
        self.verify_model()
        receipt['model_verified_before_history_commit'] = True
        receipt['generation'] = generation
        self.last_generation = generation
        if generation['finish_reason'] == 'length' and not self.allow_partial:
            self.last_error = 'output_limit'
            raise GenerationError('output_limit')
        return conversation.bounded_text(receipt['stdout'])

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def initialize():
    profile = load_profile(os.environ['ROKO_FRESH_PROFILE'])
    provider = FreshProvider(profile)
    sys.path.insert(0, str(Path(os.environ['OMEGA_PATH'])/'src'))
    import providers
    class Adapter(providers.LLMProvider):
        def chat(self, request):
            text = provider.chat([{'role':m.role,'content':m.content} for m in request.messages])
            return providers.LLMResponse().add_tool_call(providers.LLMToolCall().with_name('reply')
                .with_id('roko-reply').with_arguments({'text':text}))
    providers.registerLLMProvider('RokoFreshText', Adapter())
    providers.llmProviderStart('RokoFreshText')
    ranker = no_context
    if profile.get('ecan'):
        from fresh_ecan import rank_candidates
        def ranker(candidates, **kwargs):
            result, receipt = rank_candidates(candidates, profile=profile, **kwargs)
            provider.ecan_receipts.append(receipt)
            return result
    reasoner = None
    try:
        if 'nars_cognition' in profile:
            from cognition import NarsCognition
            config = profile['nars_cognition']
            reasoner = NarsCognition(config['manifest'], config['admission'], config['evidence_root'])
    except BaseException:
        provider.close()
        raise
    conversation.session = conversation.Session(provider, ranker, reasoner=reasoner)
    if os.environ.get('ROKO_API_VERSION') == '2':
        import durable_api
        durable_api.initialize(provider, ranker, reasoner=reasoner)
    return True


def finish():
    provider = conversation.session.provider
    try:
        provider.verify_model()
        print('ROKO_FRESH_CONVERSATION '+json.dumps({'native_calls':provider.receipts,
              'history':conversation.session.history, 'model_identity_unchanged':True,
              'model_sha256':recovered.MODEL_SHA, 'ecan_receipts':provider.ecan_receipts,
              'ecan_qualified':bool(provider.profile.get('ecan')),
              'cognitive_receipts':getattr(conversation.session.reasoner,'receipts',[]),
              'cognitive_history':conversation.session.cognitive_history,
              'mork_receipts':provider.mork_receipts}), file=sys.stderr)
    finally:
        provider.close()
    return True
