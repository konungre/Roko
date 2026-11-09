"""Authored independent Fraction oracle. NOT NACE execution or native evidence.

This is exclusively for source tests and later comparison of actual worker output.
It is never an execution fallback and is not imported by the native worker.
"""
from copy import deepcopy
from fractions import Fraction

class ReferenceCore:
    @staticmethod
    def _AddEvidence(evidence, rule, positive, w_max=20):
        pos, neg = evidence.get(rule,(0,0))
        if pos+neg < w_max+1:
            pos,neg = (pos+1,neg) if positive else (pos,neg+1)
        elif positive:
            neg = max(0,neg-1)
        else:
            pos = max(0,pos-1)
        evidence[rule] = pos,neg
        return evidence

    @staticmethod
    def Hypothesis_TruthValue(ev):
        positive,negative = ev
        count = positive+negative
        return float(Fraction(positive,count)), float(Fraction(count,count+1))

    @staticmethod
    def Hypothesis_TruthExpectation(truth):
        frequency,confidence = truth
        return confidence*(frequency-.5)+.5

    @staticmethod
    def Hypothesis_Choice(evidence, first, second):
        def expectation(rule):
            positive,negative = evidence[rule]
            return Fraction(2*positive+1,2*(positive+negative+1))
        return first if expectation(first)>expectation(second) else second

    @staticmethod
    def NACE_Predict(now,focus,world,operation,rules,customGoal=None):
        assert customGoal is None
        board,values,times = world
        attended = {(y,x) for y in range(3) for x in range(3) if board[y][x] in focus}
        originals = tuple(attended)
        for y,x in originals:
            attended.update((y+dy,x+dx) for rule in rules for dy,dx,_ in rule[0][2:])
        choices = []
        for y in range(3):
            for x in range(3):
                if (y,x) not in attended:
                    continue
                best = None
                for order,rule in enumerate(rules):
                    pre,con = rule
                    if pre[0] != operation or pre[1] != values[1:]:
                        continue
                    if any(not(0<=y+dy<3 and 0<=x+dx<3) for dy,dx,_ in pre[2:]):
                        continue
                    ratio = Fraction(sum(board[y+dy][x+dx]==value for dy,dx,value in pre[2:]),len(pre)-2)
                    if ratio == 0:
                        continue
                    rank = (ratio,len(pre),-order)
                    if best is None or rank>best[0]:
                        best = rank,rule
                if best:
                    choices.append((y,x,best[0][0],best[1]))
        highest = max((entry[2] for entry in choices),default=Fraction(0))
        newworld = deepcopy(world)
        applied = []
        for y,x,ratio,rule in choices:
            if ratio == highest:
                newworld[0][y][x] = rule[1][2]
                newworld[1] = rule[1][3]
                applied.append(ratio)
        match = sum(applied,Fraction(0))/len(applied) if applied else Fraction(1)
        # Focus ties retain insertion order, as in the upstream dict max call.
        max_focus = max(focus,key=focus.get) if focus else None
        age = max((now-times[y][x] for y,x in attended if 0<=y<3 and 0<=x<3
                   and max_focus is not None and newworld[0][y][x]==max_focus),default=0)
        score = float(match)
        if newworld[1][0] == 1 and match == 1:
            score = -float('inf')
        if newworld[1][0] == -1 and match == 1:
            score = float('inf')
        return newworld,score,age,newworld[1]
