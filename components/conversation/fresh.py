"""Fresh-build host profile, separate from the immutable recovered-host receipt.

Uses real Omega provider dispatch. No action executor or remote fallback exists.
Nonempty symbolic context requires a separately qualified ECAN integration.
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
    return profile


def no_context(candidates, **kwargs):
    raise ValueError('Native ECAN is not qualified in this fresh profile; use empty context')


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
        prompt = recovered.render(messages)
        source = Path(__file__).resolve().parent
        parent_start = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19]
        command = [self.profile['python'], '-B', str(source/'fresh_supervise.py'),
                   '--parent-pid', str(os.getpid()), '--parent-start', parent_start,
                   '--seconds', '150', '--', self.profile['infer'],
                   '--model', f'/proc/{os.getpid()}/fd/{self.fd}', '--max-tokens', '64']
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
                   'stdout':out.decode('utf-8'), 'stderr':err.decode('utf-8',errors='replace'),
                   'network_denied':True, 'executed_actions':0}
        self.receipts.append(receipt)
        if proc.returncode or len(out)>32768 or len(err)>1024**2 or b'descendants_cleaned=1' not in err:
            raise RuntimeError('Fresh native inference failed: '+str(proc.returncode))
        self.verify_model()
        receipt['model_verified_before_history_commit'] = True
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
    if 'durable_memory' in profile:
        from durable_session import open_session
        try:
            conversation.session = open_session(provider, no_context, profile)
        except BaseException:
            provider.close()
            raise
    else:
        conversation.session = conversation.Session(provider, no_context)
    return True


def finish():
    provider = conversation.session.provider
    try:
        provider.verify_model()
        print('ROKO_FRESH_CONVERSATION '+json.dumps({'native_calls':provider.receipts,
              'history':conversation.session.history, 'model_identity_unchanged':True,
              'model_sha256':recovered.MODEL_SHA, 'ecan_qualified':False,
              'mork_receipts':getattr(conversation.session,'memory_receipts',[]),
              'durable_history':hasattr(conversation.session,'store')}), file=sys.stderr)
    finally:
        try: provider.close()
        finally:
            if hasattr(conversation.session,'close'):conversation.session.close()
    return True
