"""Bounded, local Granite proposal provider for the unchanged Omega contract.

The supported text-only chat-template subset is derived from IBM's pinned
Apache-2.0 template. This is a new adapter, not the upstream network provider.
It never dispatches the proposed tools.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

import providers

ALLOWED = {'record_answer': ['text'], 'record_contact': ['name', 'city'],
           'record_invoice': ['invoice', 'total']}
TOOLS_PREFIX = ('You are a helpful assistant with access to the following tools. '
                'You may call one or more tools to assist with the user query.\n\n'
                'You are provided with function signatures within <tools></tools> XML tags:\n<tools>')
TOOLS_SUFFIX = ('\n</tools>\n\nFor each tool call, return a json object with function name and '
                'arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n'
                '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>. '
                'If a tool does not exist in the provided list of tools, notify the user '
                'that you do not have the ability to fulfill the request.')


def schema(tool):
    # Same supported schema as Omega AIProvider.convert_tool; no network import.
    return {'type': 'function', 'function': {
        'name': tool.name, 'description': tool.description, 'strict': True,
        'parameters': {'type': 'object',
                       'properties': {p.name: {'type': 'string'} for p in tool.parameters},
                       'required': [p.name for p in tool.parameters],
                       'additionalProperties': False}}}


def validate_request(request):
    if type(request) is not providers.LLMRequest:
        raise ValueError('Expected actual Omega LLMRequest')
    if type(request.max_tokens) is not int or not 1 <= request.max_tokens <= 64:
        raise ValueError('Guest output cap is 64 tokens')
    if not 1 <= len(request.tools) <= 3:
        raise ValueError('Guest tool count limit')
    names = set()
    for tool in request.tools:
        if (type(tool) is not providers.LLMTool or tool.name in names
                or tool.name not in ALLOWED
                or [p.name for p in tool.parameters] != ALLOWED[tool.name]
                or not isinstance(tool.description, str) or len(tool.description) > 256):
            raise ValueError('Only declared inert schemas are accepted')
        names.add(tool.name)
    if not 1 <= len(request.messages) <= 4:
        raise ValueError('Guest message count limit')
    for message in request.messages:
        if (type(message) is not providers.LLMMessage
                or message.role not in ('system', 'user', 'assistant')
                or not isinstance(message.content, str)):
            raise ValueError('Only plain text messages are accepted')
    if sum(len(m.content) for m in request.messages) > 2048:
        raise ValueError('Guest input character cap')
    return names


def render_prompt(request):
    validate_request(request)
    tools = TOOLS_PREFIX + ''.join('\n' + json.dumps(schema(t), ensure_ascii=False)
                                   for t in request.tools) + TOOLS_SUFFIX
    system = tools
    if request.messages[0].role == 'system':
        system = request.messages[0].content + '\n\n' + tools
    prompt = '<|start_of_role|>system<|end_of_role|>' + system + '<|end_of_text|>\n'
    for index, message in enumerate(request.messages):
        if index == 0 and message.role == 'system':
            continue
        prompt += ('<|start_of_role|>' + message.role + '<|end_of_role|>'
                   + message.content + '<|end_of_text|>\n')
    prompt += '<|start_of_role|>assistant<|end_of_role|>'
    if len(prompt.encode('utf-8')) > 16384:
        raise ValueError('Rendered prompt byte cap')
    return prompt


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse_tool(text, request):
    if len(text.encode('utf-8')) > 32768:
        raise ValueError('Output byte cap')
    match = re.fullmatch(r'\s*<tool_call>\s*(.*?)\s*</tool_call>\s*', text, re.S)
    if not match:
        raise ValueError('Expected exactly one native tool_call block')
    obj = json.loads(match[1], object_pairs_hook=unique_object)
    if not isinstance(obj, dict) or set(obj) != {'name', 'arguments'}:
        raise ValueError('Unexpected proposal envelope')
    name, args = obj['name'], obj['arguments']
    if isinstance(args, str):
        args = json.loads(args, object_pairs_hook=unique_object)
    if (not isinstance(name, str) or name not in ALLOWED
            or not request.has_tool(name) or not isinstance(args, dict)
            or set(args) != set(ALLOWED[name])
            or any(not isinstance(v, str) or len(v) > 1000 for v in args.values())):
        raise ValueError('Unapproved tool or invalid bounded arguments')
    return providers.LLMResponse().add_tool_call(
        providers.LLMToolCall().with_name(name).with_id('granite-guest-proposal-0')
        .with_arguments(args))


def tool_grammar(names):
    if not names or any(n not in ALLOWED for n in names):
        raise ValueError('Unknown grammar tools')
    alternatives = []
    for name in sorted(names):
        fields = [json.dumps(json.dumps(key)) + ' ws ":" ws string' for key in ALLOWED[name]]
        alternatives.append(json.dumps('{"name":' + json.dumps(name) + ',"arguments":{')
                            + ' ws ' + ' ws "," ws '.join(fields) + ' ws ' + json.dumps('}}'))
    return ('root ::= "<tool_call>" ws (' + ' | '.join(alternatives) + ') ws "</tool_call>"\n'
            + r'ws ::= [ \t\n\r]*' + '\n'
            + r'string ::= "\"" char* "\""' + '\n'
            + r'char ::= [^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})' + '\n')


def verified_file(path, expected, deadline):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            if time.monotonic() >= deadline:
                raise TimeoutError('Guest asset verification deadline exceeded')
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError('Guest asset hash mismatch: ' + path.name)


class GraniteGuestProvider(providers.LLMProvider):
    def __init__(self, root, *, constrained=True):
        if constrained is not True:
            raise ValueError('Guest provider requires syntax-constrained output')
        self.root = Path(root)
        self.ready = False
        self.last = {}

    def start(self):
        self.ready = False
        deadline = time.monotonic() + 120
        manifest = json.loads((self.root / 'granite-guest-runtime.lock.json').read_text())
        if manifest['status'] != 'built-and-verified':
            raise ValueError('Guest runtime has not passed binary admission')
        lock = json.loads((self.root / 'granite-model.lock.json').read_text())
        self.model = Path(lock['path'])
        if (str(self.model) != '/models/granite-4.0-h-tiny-Q4_K_M.gguf'
                or self.model.stat().st_size != lock['bytes']):
            raise ValueError('Unexpected model mount or size')
        mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
        if not any(len(row) > 5 and row[4] == '/models' and 'ro' in row[5].split(',') for row in mounts):
            raise ValueError('Model disk must be mounted read-only at /models')
        for relative, expected in manifest['files'].items():
            path = Path(relative)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Invalid runtime lock path')
            verified_file(self.root / path, expected, deadline)
        self.executable = self.root / 'runtime/granite/omega-granite-guest'
        if 'runtime/granite/omega-granite-guest' not in manifest['files']:
            raise ValueError('Unpinned guest helper')
        verified_file(self.model, lock['sha256'], deadline)
        self.ready = True

    def stop(self):
        self.ready = False

    def _render_prompt(self, request):
        return render_prompt(request)

    def _parse_output(self, text, request):
        return parse_tool(text, request)

    def chat(self, request):
        self.last = {}
        try:
            if not self.ready:
                raise ValueError('Provider not started')
            names = validate_request(request)
            prompt = self._render_prompt(request).encode('utf-8')
            args = [str(self.executable), '--model', str(self.model),
                    '--max-tokens', str(request.max_tokens), '--grammar', tool_grammar(names)]
            started = time.monotonic()
            output = {'stdout': bytearray(), 'stderr': bytearray()}
            peak = 0
            with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True,
                                  start_new_session=True,
                                  env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
                                       'OMP_NUM_THREADS': '1'}) as proc:
                try:
                    proc.stdin.write(prompt)
                    proc.stdin.close()
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ, 'stdout')
                        selector.register(proc.stderr, selectors.EVENT_READ, 'stderr')
                        while selector.get_map():
                            if time.monotonic() - started >= 310:
                                raise TimeoutError('Guest inference exceeded 310 seconds')
                            for key, _ in selector.select(.1):
                                chunk = os.read(key.fileobj.fileno(), 8192)
                                if not chunk:
                                    selector.unregister(key.fileobj)
                                    continue
                                output[key.data].extend(chunk)
                                if len(output[key.data]) > (32768 if key.data == 'stdout' else 1024 * 1024):
                                    raise ValueError('Native output stream limit exceeded')
                            try:
                                for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines():
                                    if line.startswith('VmHWM:'):
                                        peak = max(peak, int(line.split()[1]))
                            except FileNotFoundError:
                                pass
                    proc.wait(timeout=max(.1, 310 - (time.monotonic() - started)))
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=5)
            stdout = output['stdout'].decode('utf-8', errors='strict')
            self.last = {'raw_output': stdout, 'stderr': output['stderr'].decode('utf-8', errors='replace'),
                         'returncode': proc.returncode, 'elapsed_seconds': round(time.monotonic() - started, 3),
                         'peak_rss_kib': peak, 'executed_actions': 0}
            usage = re.search(r'ROKO_GRANITE_USAGE max_rss_kib=(\d+) minor_faults=(\d+) major_faults=(\d+)', self.last['stderr'])
            if usage:
                self.last.update(native_max_rss_kib=int(usage[1]),
                                 native_minor_faults=int(usage[2]), native_major_faults=int(usage[3]))
            if proc.returncode:
                raise RuntimeError('Guest inference failed: ' + str(proc.returncode))
            return self._parse_output(stdout, request)
        except Exception as error:
            return providers.LLMResponse().with_error(str(error))
