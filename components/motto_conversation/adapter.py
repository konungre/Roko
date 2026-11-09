"""Bounded typed-message transport through the actual MIT MeTTa-Motto Agent.

The callback is a transport boundary, not an LLM implementation. Production
callers must separately qualify their model, runtime closure and supervision.
"""
import hashlib
import importlib.util
import json
from pathlib import Path


def load_upstream():
    root = Path(__file__).resolve().parent / 'upstream'
    lock = json.loads((root / 'source-lock.json').read_bytes())
    for name, expected in lock['files'].items():
        raw = (root / name).read_bytes()
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('MeTTa-Motto source identity mismatch')
    spec = importlib.util.spec_from_file_location('roko_motto_upstream_agent', root / 'agent.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_messages(messages):
    if type(messages) is not list or not 1 <= len(messages) <= 32:
        raise ValueError('Require 1..32 typed messages')
    for message in messages:
        if (type(message) is not dict or set(message) != {'role', 'content'}
                or message['role'] not in ('system', 'user', 'assistant')
                or type(message['content']) is not str):
            raise ValueError('Require text roles without tools or scripts')
    if len(json.dumps(messages, ensure_ascii=False).encode()) > 16384:
        raise ValueError('Message byte cap')
    return [dict(message) for message in messages]


def chat(messages, model):
    """Return real upstream response conversion; call model exactly once.

    Content is a ValueAtom, never parsed as code. Reject upstream normalization
    rather than quietly changing the model input (notably literal backslash-n).
    """
    expected = validate_messages(messages)
    upstream = load_upstream()
    from hyperon import E, S, ValueAtom, MeTTa, GroundedAtom, Environment
    metta = MeTTa(env_builder=Environment.custom_env(config_dir=None, create_config=False))
    calls = []

    class Transport(upstream.Agent):
        def __call__(self, forwarded, functions, **params):
            if functions or params or forwarded != expected or calls:
                raise ValueError('MeTTa-Motto changed bounded transport input')
            calls.append(True)
            result = model([dict(row) for row in forwarded])
            if type(result) is not str or len(result.encode()) > 32768:
                raise ValueError('Require bounded model text')
            # Every committed assistant reply becomes a later input message.
            # atom2msg replaces literal backslash-n on that later turn; reject
            # it now rather than persisting history that cannot round-trip.
            if '\\n' in result:
                raise ValueError('Model text cannot round-trip through MeTTa-Motto')
            return upstream.Response(result)

    operation = Transport.get_agent_atom(metta)[0]
    atoms = E(S('Messages'), *(E(S(row['role']), ValueAtom(row['content'])) for row in expected))
    result = metta.evaluate_atom(E(operation, atoms))
    if len(calls) != 1 or len(result) != 1 or not isinstance(result[0], GroundedAtom):
        raise ValueError('Unexpected MeTTa-Motto transport response')
    value = result[0].get_object().value
    if type(value) is not str:
        raise ValueError('Non-text MeTTa-Motto response')
    return value
