"""Bounded NACE composition; backend supplied by the fixed worker, never request data.

The authored adapter revises explicit evidence, deterministically selects one rule
per precondition with upstream Hypothesis_Choice, then asks actual NACE_Predict
for one hypothetical 3x3 state. It never executes a named action or saves a world.
"""
import copy
import math
from typing import Protocol
from contract import PIN, InvalidRequest, parse_request, matrix, token, integer

class Core(Protocol):
    def _AddEvidence(self, evidence, rule, positive, w_max=20): ...
    def Hypothesis_TruthValue(self, evidence): ...
    def Hypothesis_TruthExpectation(self, truth): ...
    def Hypothesis_Choice(self, evidence, rule1, rule2): ...
    def NACE_Predict(self, now, focus, oldworld, operation, rules, customGoal=None): ...

class InvalidCoreResult(ValueError):
    pass

def finite_number(value, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise InvalidCoreResult('invalid finite numeric result')
    return float(value)

def transition(raw, core: Core):
    """Return hypothetical state data only. A backend call is not runtime attestation."""
    request = parse_request(raw)
    digest = request.digest()
    original = copy.deepcopy(raw)
    before = [list(map(list, request.board)), (request.reward, request.inventory), list(map(list, request.times))]
    before_saved = copy.deepcopy(before)
    evidence = {r.core(): (r.positive, r.negative) for r in request.rules}
    by_id = {r.identifier: r for r in request.rules}
    for rid, positive in request.updates:
        evidence = core._AddEvidence(evidence, by_id[rid].core(), positive, 20)
    if type(evidence) is not dict or set(evidence) != {r.core() for r in request.rules}:
        raise InvalidCoreResult('unexpected evidence keys')
    truth = []
    for rule in request.rules:
        ev = evidence[rule.core()]
        if type(ev) is not tuple or len(ev) != 2 or any(type(v) is not int or v < 0 for v in ev) or not 1 <= sum(ev) <= 21:
            raise InvalidCoreResult('invalid revised evidence')
        tv = core.Hypothesis_TruthValue(ev)
        if type(tv) not in (list,tuple) or len(tv) != 2:
            raise InvalidCoreResult('invalid truth shape')
        truth.append({'id': rule.identifier, 'evidence': list(ev),
                      'frequency': finite_number(tv[0],0,1),
                      'confidence': finite_number(tv[1],0,1),
                      'expectation': finite_number(core.Hypothesis_TruthExpectation(tv),0,1)})
    selected = {}
    for rule in request.rules:
        key = rule.core()[0]
        if key in selected:
            prior = selected[key]
            winner = core.Hypothesis_Choice(evidence, prior.core(), rule.core())
            if winner == rule.core():
                selected[key] = rule
            elif winner != prior.core():
                raise InvalidCoreResult('choice invented a rule')
        else:
            selected[key] = rule
    result = core.NACE_Predict(request.now, dict(request.focus), before, request.operation,
                               tuple(r.core() for r in selected.values()), None)
    if raw != original or before != before_saved or request.digest() != digest:
        raise InvalidCoreResult('input state was mutated')
    if type(result) not in (list,tuple) or len(result) != 4:
        raise InvalidCoreResult('invalid prediction tuple')
    world, score, age, values = result
    try:
        if type(world) is not list or len(world) != 3:
            raise InvalidCoreResult('invalid world')
        board = matrix(world[0], token)
        times = matrix(world[2], lambda x: integer(x,0,request.now))
        if times != request.times or type(world[1]) is not tuple or len(world[1]) != 2 or values != world[1]:
            raise InvalidCoreResult('world values or times inconsistent')
        vals = [integer(world[1][0],-1,1), integer(world[1][1],0,4)]
        integer(age,0,request.now)
    except InvalidRequest as e:
        raise InvalidCoreResult(str(e)) from e
    if type(score) not in (int,float) or math.isnan(score):
        raise InvalidCoreResult('invalid prediction score')
    if score == -math.inf:
        if vals[0] != 1:
            raise InvalidCoreResult('reward sentinel without positive reward')
        category, match_score = 'certain_reward', None
    elif score == math.inf:
        if vals[0] != -1:
            raise InvalidCoreResult('penalty sentinel without negative reward')
        category, match_score = 'certain_penalty', None
    else:
        category, match_score = 'finite_match_score', finite_number(score,0,1)
    return {'schema': 'roko.nace.predictive-adaptation.v1', 'upstream_commit': PIN,
            'request_sha256': digest, 'revised_truth': truth,
            'selected_rules': [r.identifier for r in selected.values()],
            'prediction': {'board': list(map(list,board)), 'values': vals,
                           'times': list(map(list,times)), 'focus_age': age,
                           'score_kind': category, 'match_score': match_score},
            'input_unchanged': True, 'state_scope': 'hypothetical_fixture_only',
            'authority': False, 'external_actions': 0}
