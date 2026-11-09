"""Optional, ephemeral MORK fact lookup. No rules, actions, or durable graph.

Typed caller symbols are tokenized, never evaluated. Process isolation and bounds
reduce exposure; they do not repair upstream native parser/FFI vulnerabilities.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_FACTS = 16
MAX_ARITY = 3
MAX_IDENTIFIER = 16
MAX_REQUEST_BYTES = 2048
MAX_ATOM_BYTES = 1024
MAX_QUERY_BYTES = 256
MAX_RESULT_BYTES = 1024
MAX_OUTPUT_BYTES = 4096
MAX_STDERR_BYTES = 1024
PINNED_LIBRARIES = {
    'target/release/libmork_ffi.so': '4e0d9fe13b7766cb8f16182e3fbbb8c428ed4d43d605f552232488d8d3f30a20',
    'morklib.so': '78c965ad5798363b1b5b3796921742f5a98a34ab11d60bd488454d6e303296b5',
}
CHILD_FILE_HASHES = {'scripts/no-network.py': 'f1fb45f73f8f5942297a7c2b13bb70493caee26993d8d708c01ee84704b81ddd', 'integration/mork_child_limits.py': 'ae98c6727cc87d1c4509b0e5d7b6cab1b2485e9e70aeb1a41ef3aa5726158506', 'integration/mork_query_worker.pl': '6c964aaa8553ba7c6cad2516e2212086ed859c4253d00f8435f86f1b69c143d2'}
SWIPL_SHA256 = '79799b39f2dd8e551a8f96df1ff2e71949529bf221724cbec3078c75d31d4c02'
IDENTIFIER = re.compile(r'[a-z][a-z0-9_]{0,15}\Z', re.ASCII)

class NativeMORKError(RuntimeError):
    """Unavailable, altered, failed, timed-out, or invalid native execution."""

def _identifier(value):
    if type(value) is not str or IDENTIFIER.fullmatch(value) is None:
        raise ValueError('Identifiers must be 1..16 lowercase ASCII letters/digits/underscores, starting with a letter')
    return value

def _row(row, *, pattern=False):
    if type(row) is not dict or set(row) != {'relation', 'args'}:
        raise ValueError('Each fact/query requires exactly relation and args')
    relation = _identifier(row['relation'])
    if type(row['args']) is not list or not 1 <= len(row['args']) <= MAX_ARITY:
        raise ValueError('Expected 1..3 arguments')
    args = [None if pattern and x is None else _identifier(x) for x in row['args']]
    return {'relation': relation, 'args': args}

def _validate(facts, query, timeout):
    if type(facts) is not list or not 0 <= len(facts) <= MAX_FACTS:
        raise ValueError('Expected 0..16 facts')
    if type(timeout) is not int or not 1 <= timeout <= 5:
        raise ValueError('timeout must be an integer in 1..5 seconds')
    facts = [_row(f) for f in facts]
    query = _row(query, pattern=True)
    arities = {query['relation']: len(query['args'])}
    for fact in facts:
        if arities.setdefault(fact['relation'], len(fact['args'])) != len(fact['args']):
            raise ValueError('A relation must have one consistent arity')
    request = json.dumps({'facts': facts, 'query': query}, separators=(',', ':')).encode('ascii')
    if len(request) > MAX_REQUEST_BYTES:
        raise ValueError('Typed request exceeds 2048 bytes')
    return facts, query

def _encode(facts, query):
    symbols = sorted({x for row in facts + [query] for x in [row['relation']] + row['args'] if x is not None})
    encode = {symbol: 's'+str(i) for i, symbol in enumerate(symbols)}
    decode = {v: k for k, v in encode.items()}
    def atom(row, pattern=False):
        terms = [encode[row['relation']]]
        terms += ['$v'+str(i) if x is None and pattern else encode[x] for i,x in enumerate(row['args'])]
        return '('+' '.join(terms)+')'
    atoms = ' '.join(sorted({atom(row) for row in facts}))
    pattern = atom(query, True)
    query_text = '('+pattern+' '+pattern+')'
    if len(atoms.encode('ascii')) > MAX_ATOM_BYTES or len(query_text.encode('ascii')) > MAX_QUERY_BYTES:
        raise ValueError('Generated native request exceeds safe adapter limits')
    return {'atoms': atoms, 'query': query_text}, decode

def _decode(output, facts, query, decode):
    try: text = output.decode('ascii')
    except UnicodeError as exc: raise NativeMORKError('Invalid native response encoding') from exc
    header, footer = 'MORK_FACTS_V1\n', 'MORK_END\n'
    if not text.startswith(header) or not text.endswith(footer):
        raise NativeMORKError('Invalid native response envelope')
    rows = text[len(header):-len(footer)]
    if not rows.isascii() or len(rows) > MAX_RESULT_BYTES:
        raise NativeMORKError('Native result limit exceeded')
    lines = rows.splitlines()
    if len(lines) > MAX_FACTS or any(not x for x in lines) or (rows and not rows.endswith('\n')):
        raise NativeMORKError('Invalid native result framing')
    actual = []
    for line in lines:
        if re.fullmatch(r'\(s[0-9]+(?: s[0-9]+){1,3}\)', line, re.ASCII) is None:
            raise NativeMORKError('Invalid native fact syntax')
        try: values = [decode[token] for token in line[1:-1].split(' ')]
        except KeyError as exc: raise NativeMORKError('Unknown native symbol') from exc
        actual.append((values[0], tuple(values[1:])))
    if len(actual) != len(set(actual)):
        raise NativeMORKError('Duplicate native results')
    # Fail closed on missing, additional, or mismatched facts. This tiny equality
    # lookup is independently checked; a native failure is never replaced by it.
    expected = {(f['relation'], tuple(f['args'])) for f in facts
                if f['relation'] == query['relation'] and len(f['args']) == len(query['args'])
                and all(q is None or q == x for q,x in zip(query['args'], f['args']))}
    if set(actual) != expected:
        raise NativeMORKError('Native result disagrees with bounded fact contract')
    return [{'relation': relation, 'args': list(args)} for relation,args in sorted(actual)]

def _kill(process):
    try: os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    process.wait()

def _run(command, payload, *, cwd, env, timeout):
    deadline = time.monotonic() + timeout
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, close_fds=True)
    except OSError as exc: raise NativeMORKError('Native process unavailable') from exc
    buffers = {'out': bytearray(), 'err': bytearray()}
    try:
        # Payload is less than PIPE_BUF; there is no unbounded stdin producer.
        process.stdin.write(payload); process.stdin.close()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, ('out', MAX_OUTPUT_BYTES))
            selector.register(process.stderr, selectors.EVENT_READ, ('err', MAX_STDERR_BYTES))
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise NativeMORKError('Native process timed out')
                for key, _ in selector.select(remaining):
                    name, limit = key.data
                    chunk = os.read(key.fd, min(1024, limit + 1 - len(buffers[name])))
                    if not chunk: selector.unregister(key.fileobj); continue
                    buffers[name].extend(chunk)
                    if len(buffers[name]) > limit: raise NativeMORKError('Native process output limit exceeded')
        try: process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc: raise NativeMORKError('Native process timed out') from exc
        if process.returncode != 0 or buffers['err']:
            raise NativeMORKError('Native process failed; no facts returned')
        return bytes(buffers['out'])
    except (OSError, BrokenPipeError) as exc:
        raise NativeMORKError('Native process communication failed') from exc
    finally:
        # Kill any descendants even if the direct child already exited.
        _kill(process)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe and not pipe.closed: pipe.close()

def query_facts(facts, query, *, timeout=3, root=ROOT):
    """Query a fresh native space with typed facts and independent None wildcards.

    Returns detached, advisory facts. No executable MeTTa, repeated-variable
    logic, MM2, persistence, controller integration, or authorization API exists.
    Requires separately acquired, approved and hash-pinned development binaries.
    """
    facts, query = _validate(facts, query, timeout)
    request, decode = _encode(facts, query)
    root = Path(root).resolve()
    ffi = root/'build-src/mork-stage/PeTTa/mork_ffi'
    for relative, expected in PINNED_LIBRARIES.items():
        try: actual = hashlib.sha256((ffi/relative).read_bytes()).hexdigest()
        except OSError as exc: raise NativeMORKError('Optional native MORK runtime is unavailable; it is excluded from distribution') from exc
        if actual != expected: raise NativeMORKError('Native MORK binary hash mismatch')
    swipl = root/'runtime/swipl/bin/swipl'
    scripts = [root/'scripts/no-network.py', root/'integration/mork_child_limits.py', root/'integration/mork_query_worker.pl']
    if not swipl.is_file() or any(not p.is_file() for p in scripts):
        raise NativeMORKError('Native MORK child runtime is incomplete')
    try:
        if hashlib.sha256(swipl.read_bytes()).hexdigest() != SWIPL_SHA256:
            raise NativeMORKError('SWI-Prolog binary hash mismatch')
        for relative, expected in CHILD_FILE_HASHES.items():
            if hashlib.sha256((root/relative).read_bytes()).hexdigest() != expected:
                raise NativeMORKError('Native child helper hash mismatch')
    except OSError as exc:
        raise NativeMORKError('Native child runtime cannot be read') from exc
    payload = (request['atoms']+'\n'+request['query']+'\n').encode('ascii')
    if len(payload) > 2048: raise NativeMORKError('Encoded protocol limit exceeded')
    with tempfile.TemporaryDirectory(prefix='mork-facts-', dir=root) as directory:
        env = {'PATH':'/usr/bin:/bin', 'HOME':directory, 'TMPDIR':directory,
               'LD_LIBRARY_PATH':str(root/'runtime/swipl/lib/x86_64-linux'), 'LANG':'C', 'OMP_NUM_THREADS':'1'}
        command = [sys.executable, str(scripts[0]), sys.executable, str(scripts[1]),
                   str(ffi/'target/release/libmork_ffi.so'), str(swipl), str(scripts[2]), str(ffi/'morklib.so')]
        output = _run(command, payload, cwd=directory, env=env, timeout=timeout)
    return {'implementation':'native-mork-bounded-facts', 'facts':_decode(output, facts, query, decode),
            'advisory_only':True, 'authorizes_actions':False, 'persistent_state_changed':False,
            'fresh_process':True, 'network_denied':True}
