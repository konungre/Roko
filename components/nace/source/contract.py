"""Closed, immutable fixture contract. No callables, commands or persistent actions."""
from dataclasses import dataclass
from hashlib import sha256
import json

PIN = '361fddf5f6885a60b6d5e0d179e0394da876df4c'
TOKENS = frozenset(('.', 'x', 'f', 'o', 'k', 'u'))
ACTIONS = frozenset(('left', 'right', 'up', 'down', 'observe'))

class InvalidRequest(ValueError):
    pass

def integer(x, lo, hi):
    if type(x) is not int or not lo <= x <= hi:
        raise InvalidRequest('integer outside contract')
    return x

def sequence(x, lo, hi):
    if type(x) not in (list, tuple) or not lo <= len(x) <= hi:
        raise InvalidRequest('sequence outside contract')
    return x

def fields(x, names):
    if type(x) is not dict or set(x) != set(names):
        raise InvalidRequest('unexpected or missing fields')

def token(x):
    if type(x) is not str or x not in TOKENS:
        raise InvalidRequest('unknown token')
    return x

def action(x):
    if type(x) is not str or x not in ACTIONS:
        raise InvalidRequest('unknown inert action')
    return x

def matrix(x, convert):
    return tuple(tuple(convert(v) for v in sequence(row, 3, 3)) for row in sequence(x, 3, 3))

@dataclass(frozen=True)
class Rule:
    identifier: str
    operation: str
    inventory: int
    conditions: tuple
    result: str
    reward: int
    result_inventory: int
    positive: int
    negative: int

    def core(self):
        return ((self.operation, (self.inventory,), *self.conditions),
                (0, 0, self.result, (self.reward, self.result_inventory)))

@dataclass(frozen=True)
class Request:
    board: tuple
    reward: int
    inventory: int
    times: tuple
    now: int
    focus: tuple
    operation: str
    rules: tuple
    updates: tuple

    def canonical(self):
        return {'board': self.board, 'reward': self.reward, 'inventory': self.inventory,
                'times': self.times, 'now': self.now, 'focus': self.focus,
                'action': self.operation,
                'rules': [r.__dict__ for r in self.rules], 'updates': self.updates}

    def digest(self):
        return sha256(json.dumps(self.canonical(), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def parse_request(raw):
    fields(raw, ('board','values','times','now','focus','action','rules','updates'))
    now = integer(raw['now'], 0, 1000)
    board = matrix(raw['board'], token)
    times = matrix(raw['times'], lambda x: integer(x, 0, now))
    values = sequence(raw['values'], 2, 2)
    reward, inventory = integer(values[0], -1, 1), integer(values[1], 0, 4)
    focus = []
    for pair in sequence(raw['focus'], 0, 4):
        pair = sequence(pair, 2, 2)
        focus.append((token(pair[0]), integer(pair[1], 1, 100)))
    if len({x[0] for x in focus}) != len(focus):
        raise InvalidRequest('duplicate focus')
    rules = []
    for index, item in enumerate(sequence(raw['rules'], 0, 8)):
        fields(item, ('id','action','inventory','conditions','result','values','evidence'))
        if item['id'] != 'r' + str(index) or type(item['id']) is not str:
            raise InvalidRequest('rule IDs must be ordered r0..r7')
        conditions = []
        for condition in sequence(item['conditions'], 1, 4):
            dy, dx, tok = sequence(condition, 3, 3)
            integer(dy, -2, 2); integer(dx, -2, 2)
            if dy != 0 and dx != 0:
                raise InvalidRequest('only upstream cardinal neighborhoods accepted')
            conditions.append((dy, dx, token(tok)))
        if len({(y,x) for y,x,_ in conditions}) != len(conditions):
            raise InvalidRequest('duplicate condition position')
        evidence = sequence(item['evidence'], 2, 2)
        positive, negative = (integer(x, 0, 21) for x in evidence)
        if not 1 <= positive + negative <= 21:
            raise InvalidRequest('evidence total must be 1..21')
        vals = sequence(item['values'], 2, 2)
        rules.append(Rule(item['id'], action(item['action']), integer(item['inventory'],0,4),
                          tuple(conditions), token(item['result']), integer(vals[0],-1,1),
                          integer(vals[1],0,4), positive, negative))
    if len({r.core() for r in rules}) != len(rules):
        raise InvalidRequest('duplicate core rule')
    updates = []
    for update in sequence(raw['updates'], 0, 8):
        rid, positive = sequence(update, 2, 2)
        if type(rid) is not str or rid not in {r.identifier for r in rules} or type(positive) is not bool:
            raise InvalidRequest('update must name an existing rule and boolean evidence')
        updates.append((rid, positive))
    return Request(board,reward,inventory,times,now,tuple(focus),action(raw['action']),tuple(rules),tuple(updates))
