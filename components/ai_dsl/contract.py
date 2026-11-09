"""Bounded AI-DSL search contract and independent unary-composition checker."""
import hashlib
import json

SERVICES = {
    'speech2text-en.MkAudio': ('Bytes', 'speech2text-en.Audio'),
    'speech2text-en.Audio.data': ('speech2text-en.Audio', 'Bytes'),
    'speech2text-en.MkText': ('String', 'speech2text-en.Text'),
    'speech2text-en.Text.text': ('speech2text-en.Text', 'String'),
    'speech2text-en.s2t': ('speech2text-en.Audio', 'speech2text-en.Text'),
    'text-emotions.MkInput': ('String', 'text-emotions.Input'),
    'text-emotions.Input.text': ('text-emotions.Input', 'String'),
    'text-emotions.MkOutput': ('String', 'text-emotions.Output'),
    'text-emotions.Output.result': ('text-emotions.Output', 'String'),
    'text-emotions.recognize': ('text-emotions.Input', 'text-emotions.Output'),
}
GOALS = {
    'speech_to_text': ('speech2text-en.Audio', 'speech2text-en.Text', ['speech2text-en.s2t']),
    'bytes_to_text': ('Bytes', 'speech2text-en.Text', ['speech2text-en.s2t']),
    'speech_emotion': ('speech2text-en.Audio', 'text-emotions.Output',
                       ['speech2text-en.s2t', 'text-emotions.recognize']),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def validate(request):
    if (type(request) is not dict or set(request) != {'version', 'goal', 'depth'}
            or type(request['version']) is not int or request['version'] != 1
            or type(request['goal']) is not str or request['goal'] not in GOALS
            or type(request['depth']) is not int or not 0 <= request['depth'] <= 4):
        raise ValueError('Require bounded AI-DSL goal and depth 0..4')
    return dict(request)


def infer(program, budget=16):
    if budget <= 0:
        raise ValueError('Composition size cap')
    if type(program) is str and program in SERVICES:
        source, target = SERVICES[program]
        return source, target, [program]
    if (type(program) is not list or len(program) != 2 or type(program[0]) is not list
            or len(program[0]) != 2 or program[0][0] != '.'):
        raise ValueError('Unknown composition or service')
    source, middle, first = infer(program[1], budget-1)
    required, target, last = infer(program[0][1], budget-1)
    if middle != required:
        raise ValueError('Composition type mismatch')
    return source, target, first + last


def proof_depth(program):
    if type(program) is str:
        return 0
    return max(2 + proof_depth(program[0][1]), 1 + proof_depth(program[1]))


def check(request, proofs):
    request = validate(request)
    if type(proofs) is not list or len(proofs) > 64:
        raise ValueError('Proof count cap')
    source, target, required = GOALS[request['goal']]
    accepted = []
    rejected = []
    for proof in proofs:
        if (type(proof) is not list or len(proof) != 3 or proof[0] != ':'
                or proof[2] != ['->', source, target]):
            raise ValueError('Unexpected native theorem')
        actual_source, actual_target, pipeline = infer(proof[1])
        if proof_depth(proof[1]) > request['depth']:
            raise ValueError('Native proof exceeds requested search depth')
        if (actual_source, actual_target) != (source, target):
            raise ValueError('Native proof failed independent type check')
        missing = [name for name in required if name not in pipeline]
        record = {'proof': proof, 'pipeline': pipeline}
        if missing:
            rejected.append({**record, 'reason': 'missing_required_service', 'missing': missing})
        else:
            accepted.append(record)
    return {'version':1, 'request_sha256':hashlib.sha256(canonical(request)).hexdigest(),
            'goal':request['goal'], 'search_depth':request['depth'], 'accepted':accepted,
            'rejected':rejected, 'native_proof_count':len(proofs), 'executed_services':0,
            'executed_actions':0, 'service_results':None,
            'scope':'bounded_upstream_type_composition_search_with_capability_filter'}
