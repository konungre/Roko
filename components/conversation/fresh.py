"""Fresh-build host profile, separate from the immutable recovered-host receipt.

Uses real Omega provider dispatch. No action executor or remote fallback exists.
Symbolic context requires a separately qualified native ECAN profile.
"""
import base64
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


def budget_contract(profile):
    default={'kind':'roko-native-budget-v1','input_tokens':512,'context_tokens':1024,'max_output_tokens':128}
    if 'native_budget' not in profile:return default
    value=profile['native_budget']
    if (type(value) is not dict or set(value)!=set(default) or value.get('kind')!=default['kind']
            or any(type(value[k]) is not int for k in ('input_tokens','context_tokens','max_output_tokens'))
            or (value['input_tokens'],value['context_tokens'],value['max_output_tokens']) not in ((512,1024,128),(768,1024,128))):
        raise ValueError('Unsupported native budget contract')
    return dict(value)

def verify_budget_capability(profile):
    expected=budget_contract(profile)
    if 'native_budget' not in profile:return
    source=Path(__file__).resolve().parent
    stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
    command=[profile['python'],'-B',str(source/'fresh_supervise.py'),'--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','4','--',profile['infer'],'--capabilities']
    proc=subprocess.run(command,capture_output=True,timeout=5,start_new_session=True,
                        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
    if proc.returncode or len(proc.stdout)>4096 or len(proc.stderr)>4096 or b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1' not in proc.stderr:
        raise ValueError('Native budget capability probe failed')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate budget capability field')
            result[key]=value
        return result
    actual=json.loads(proc.stdout,object_pairs_hook=unique)
    if (type(actual) is not dict or set(actual)!=set(expected)
            or any(type(actual[k]) is not type(expected[k]) for k in expected) or actual!=expected):
        raise ValueError('Native budget capability mismatch')

def load_profile(path):
    profile = json.loads(Path(path).read_text())
    if profile.get('kind') != 'roko-fresh-host-v1':
        raise ValueError('Require explicit fresh-build profile')
    if 'context_projection' in profile and profile['context_projection'] != 'extractive_v1':
        raise ValueError('Unsupported context projection capability')
    for name, expected in profile['files'].items():
        if not Path(name).is_absolute() or digest(name) != expected:
            raise ValueError('Fresh closure mismatch: ' + name)
    for key in ('model', 'infer', 'swipl', 'python'):
        if profile[key] not in profile['files']:
            raise ValueError('Unpinned executable or model: ' + key)
    if profile['files'][profile['model']] != recovered.MODEL_SHA:
        raise ValueError('Unexpected Granite model identity')
    verify_budget_capability(profile)
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
    if 'learning_components' in profile:
        from learning import validate_profile
        validate_profile(profile)
    if 'motto_transport' in profile:
        from motto import validate_profile
        validate_profile(profile)
    if 'package_awareness' in profile:
        from package_awareness import validate_profile
        validate_profile(profile)
    return profile


def no_context(candidates, **kwargs):
    raise ValueError('Native ECAN is not qualified in this fresh profile; use empty context')


class GenerationError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def generation_metadata(stderr, max_tokens, input_limit=512):
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
    if not 1 <= row['input_tokens'] <= input_limit:
        raise GenerationError('invalid_generation_receipt')
    return row


def decode_output(raw, generation, receipt):
    """Only a token-limit cut inside the final UTF-8 code point is repairable."""
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as original:
        # infer appends one newline after generation; it is not a model token.
        suffix = b'\n' if raw.endswith(b'\n') else b''
        payload = raw[:-1] if suffix else raw
        try:
            payload.decode('utf-8')
        except UnicodeDecodeError as error:
            if (generation['finish_reason'] == 'length'
                    and error.reason == 'unexpected end of data'
                    and error.end == len(payload)):
                receipt['stdout_encoding'] = {
                    'encoding':'utf-8', 'status':'incomplete_suffix_replaced',
                    'replacement':'U+FFFD', 'byte_offset':error.start,
                    'byte_count':error.end-error.start,
                    'suffix_hex':payload[error.start:].hex(),
                    'native_newline_preserved':bool(suffix)}
                return payload[:error.start].decode('utf-8') + '\ufffd' + suffix.decode('ascii')
        receipt['stdout_encoding'] = {'encoding':'utf-8', 'status':'invalid',
            'byte_offset':original.start, 'byte_end':original.end,
            'reason':original.reason}
        raise GenerationError('invalid_output_encoding') from original
    receipt['stdout_encoding'] = {'encoding':'utf-8', 'status':'valid'}
    return text


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
        self.input_token_limit = budget_contract(profile)['input_tokens']
        self.receipts = []
        self.ecan_receipts = []
        self.mork_receipts = []
        self.context_policy = 'complete'
        self.model_context = None
        self.token_counter_receipts = []
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

    def _count_tokens(self, prompt, deadline):
        started = time.monotonic()
        call_deadline = min(deadline, started + 10)
        budget = call_deadline - started
        if budget <= 0.5:
            raise GenerationError('context_projection_limit')
        raw_prompt = prompt.encode('utf-8')
        receipt = {'prompt_sha256':hashlib.sha256(raw_prompt).hexdigest(),
                   'prompt_bytes':len(raw_prompt), 'network_denied':True,
                   'executed_actions':0, 'mode':'count_tokens'}
        self.token_counter_receipts.append(receipt)
        source = Path(__file__).resolve().parent
        parent_start = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')', 1)[1].split()[19]
        command = [self.profile['python'], '-B', str(source/'fresh_supervise.py'),
                   '--parent-pid', str(os.getpid()), '--parent-start', parent_start,
                   '--seconds', str(budget - 0.5), '--', self.profile['infer'],
                   '--model', f'/proc/{os.getpid()}/fd/{self.fd}', '--count-tokens']
        proc = None
        out, err = b'', b''
        try:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
                env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
                     'OMP_NUM_THREADS':'4','PYTHONDONTWRITEBYTECODE':'1'})
            try:
                out, err = proc.communicate(raw_prompt,
                    timeout=max(0.001, call_deadline - time.monotonic() - 0.25))
            except BaseException as error:
                if isinstance(error, subprocess.TimeoutExpired):
                    out, err = error.output or b'', error.stderr or b''
                proc.terminate()
                try:
                    out, err = proc.communicate(timeout=max(0.001,
                        min(0.25, call_deadline - time.monotonic())))
                except subprocess.TimeoutExpired as cleanup:
                    out, err = cleanup.output or out, cleanup.stderr or err
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=max(0.001, call_deadline - time.monotonic()))
                    receipt['cleanup'] = 'process_group_killed'
                else:
                    receipt['cleanup'] = 'terminated_and_reaped'
                if isinstance(error, subprocess.TimeoutExpired):
                    raise GenerationError('context_projection_limit') from error
                raise
            if time.monotonic() > deadline:
                raise GenerationError('context_projection_limit')
            if (proc.returncode or len(out)>4096 or len(err)>1024**2
                    or b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1' not in err):
                raise GenerationError('context_projection_failed')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('Duplicate tokenizer receipt key')
                    result[key] = value
                return result
            try:
                packet = json.loads(out.decode('utf-8'), object_pairs_hook=unique)
            except (ValueError, UnicodeDecodeError) as error:
                raise GenerationError('invalid_token_count_receipt') from error
            if (type(packet) is not dict or set(packet) != {'input_tokens'}
                    or type(packet['input_tokens']) is not int or packet['input_tokens'] <= 0):
                raise GenerationError('invalid_token_count_receipt')
            receipt['input_tokens'] = packet['input_tokens']
            return packet['input_tokens']
        except BaseException as error:
            receipt['error'] = getattr(error, 'code', type(error).__name__)
            raise
        finally:
            receipt.update(returncode=proc.returncode if proc is not None else None,
                seconds=round(time.monotonic()-started,3),
                stdout_base64=base64.b64encode(out).decode('ascii'),
                stdout_sha256=hashlib.sha256(out).hexdigest(),
                stderr_base64=base64.b64encode(err).decode('ascii'),
                stderr=err.decode('utf-8',errors='replace'))

    def _project_context(self, messages):
        from context_summary import build_summary, SummaryBudgetError
        deadline = time.monotonic() + 30
        def counter(prompt):
            return self._count_tokens(prompt, deadline)
        try:
            try:
                full_prompt = recovered.render(messages)
            except ValueError as error:
                if str(error)!='Prompt byte cap':
                    raise
                full_prompt = None
            full_count = counter(full_prompt) if full_prompt is not None else None
            if full_count is not None and full_count <= budget_contract(self.profile)['input_tokens']:
                history = json.dumps(messages[1:-1], sort_keys=True,
                    separators=(',', ':'), ensure_ascii=False)
                metadata = {'policy':'extractive_v1', 'model_context_complete':True,
                    'token_count':full_count, 'budget':budget_contract(self.profile)['input_tokens'],
                    'prompt_sha256':hashlib.sha256(full_prompt.encode()).hexdigest(),
                    'full_history_sha256':hashlib.sha256(history.encode()).hexdigest(),
                    'omitted_count':0, 'omitted_assistant_count':0,
                    'authoritative_history_changed':False}
                return messages, metadata
            session = conversation.session
            projected, metadata = build_summary(messages[1:-1], messages[-1]['content'],
                count_tokens=counter, budget=budget_contract(self.profile)['input_tokens'], recent_pairs=1,
                context=session.context, cognitive_context=session.cognitive_context,
                package_context=getattr(session,'package_context',[]))
            if time.monotonic() > deadline:
                raise GenerationError('context_projection_limit')
            return projected, dict(metadata, policy='extractive_v1',
                full_input_tokens=full_count,
                full_count_unavailable_reason='renderer_byte_cap' if full_count is None else None)
        except SummaryBudgetError as error:
            raise GenerationError('context_projection_limit') from error

    def chat(self, messages):
        self.last_generation = None
        self.last_error = None
        self.model_context = None
        if not hasattr(self, 'token_counter_receipts'):
            self.token_counter_receipts = []
        model_context = None
        policy = getattr(self, 'context_policy', 'complete')
        if policy != 'complete':
            if policy != 'extractive_v1' or self.profile.get('context_projection') != policy:
                self.last_error = 'unsupported_context_policy'
                raise GenerationError(self.last_error)
            try:
                messages, model_context = self._project_context(messages)
            except GenerationError as error:
                self.last_error = error.code
                raise
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
                   'stdout_base64':base64.b64encode(out).decode('ascii'),
                   'stdout_sha256':hashlib.sha256(out).hexdigest(),
                   'stdout_bytes':len(out), 'stderr':err.decode('utf-8',errors='replace'),
                   'network_denied':True, 'executed_actions':0}
        self.receipts.append(receipt)
        # Supervisor termination precedes generation finalization. Preserve the
        # actual resource failure instead of reporting missing model metadata.
        terminal = [line for line in receipt['stderr'].splitlines()
                    if line.startswith('ROKO_SUPERVISOR ')]
        reasons = {
            'ROKO_SUPERVISOR reason=native-deadline descendants_cleaned=1':(124,'native_timeout'),
            'ROKO_SUPERVISOR reason=native-tree-rss-cap descendants_cleaned=1':(125,'resource_limit'),
            'ROKO_SUPERVISOR reason=host-available-reserve descendants_cleaned=1':(125,'resource_limit'),
            'ROKO_SUPERVISOR reason=caller-cancelled-or-exited descendants_cleaned=1':(125,'native_cancelled')}
        if len(terminal)==1 and terminal[0] in reasons:
            expected, code = reasons[terminal[0]]
            if proc.returncode == expected:
                self.last_error = code
                receipt['terminal_error'] = code
                raise GenerationError(code)
        try:
            generation = generation_metadata(receipt['stderr'], self.max_tokens, budget_contract(self.profile)['input_tokens'])
            receipt['generation'] = generation
            self.last_generation = generation
        except GenerationError as error:
            self.last_error = error.code
            raise
        if proc.returncode or len(out)>32768 or len(err)>1024**2 or b'descendants_cleaned=1' not in err:
            raise RuntimeError('Fresh native inference failed: '+str(proc.returncode))
        if model_context is not None and generation['input_tokens'] != model_context['token_count']:
            self.last_error = 'context_projection_failed'
            raise GenerationError(self.last_error)
        self.verify_model()
        receipt['model_verified_before_history_commit'] = True
        try:
            receipt['stdout'] = decode_output(out, generation, receipt)
        except GenerationError as error:
            self.last_error = error.code
            raise
        if generation['finish_reason'] == 'length' and not self.allow_partial:
            self.last_error = 'output_limit'
            raise GenerationError('output_limit')
        text = conversation.bounded_text(receipt['stdout'])
        self.model_context = model_context
        if model_context is not None:
            receipt['model_context'] = model_context
        return text

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def initialize():
    profile = load_profile(os.environ['ROKO_FRESH_PROFILE'])
    provider = FreshProvider(profile)
    provider.motto = None
    if 'motto_transport' in profile:
        try:
            if os.environ.get('ROKO_API_VERSION') != '2':
                raise ValueError('Motto transport requires durable v2')
            from motto import MottoTransport
            provider.motto = MottoTransport(provider)
            provider.chat = provider.motto.chat
        except BaseException:
            provider.close()
            raise
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
    provider.learning = None
    provider.package_awareness = None
    try:
        if 'package_awareness' in profile:
            if os.environ.get('ROKO_API_VERSION')!='2':raise ValueError('Package awareness requires durable v2')
            from package_awareness import create_awareness
            provider.package_awareness=create_awareness(profile)
        if 'learning_components' in profile:
            from learning import LearningComponents
            provider.learning = LearningComponents(profile)
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
              'learning_receipts':getattr(provider.learning,'receipts',[]),
              'motto_receipts':getattr(provider.motto,'receipts',[]),
              'mork_receipts':provider.mork_receipts,
              'token_counter_calls':provider.token_counter_receipts,
              'package_awareness_receipts':getattr(getattr(provider,'package_awareness',None),'receipts',[])}), file=sys.stderr)
    finally:
        provider.close()
    return True
