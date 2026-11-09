# Generated from exact MIT-licensed upstream function bytes; do not edit.
# No upstream module imports or top-level simulation initialization are retained.
# Fixed 3x3 fixture world. Operation names are inert strings, never callables.
from copy import deepcopy
BOARD, VALUES, TIMES = 0, 1, 2
width, height = 3, 3
"""
 * The MIT License
 *
 * Copyright (c) 2024 Patrick Hammer, Peter Isaev
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 * """

def NACE_Predict(Time, FocusSet, oldworld, action, rules, customGoal = None):
    newworld = deepcopy(oldworld)
    used_rules_sumscore = 0.0
    used_rules_amount = 0
    (positionscores, highesthighscore) = _MatchHypotheses(FocusSet, oldworld, action, rules)
    max_focus = None
    if len(FocusSet) > 0:
        max_focus = max(FocusSet, key=lambda k: FocusSet[k])
    age = 0
    for y in range(height):
        for x in range(width):
            if (y,x) not in positionscores:
                continue
            scores, highscore, rule = positionscores[(y,x)]
            #for rule in rules:
            if _RuleApplicable(scores, highscore, highesthighscore, rule):
                newworld[VALUES] = rule[1][3]
                newworld[BOARD][y][x] = rule[1][2]
                used_rules_sumscore += scores.get(rule, 0.0)
                used_rules_amount += 1
    for y in range(height):
        for x in range(width):
            if (y,x) not in positionscores:
                continue
            if max_focus and newworld[BOARD][y][x] in FocusSet and newworld[BOARD][y][x] == max_focus:
                age = max(age, (Time - newworld[TIMES][y][x]))
    score = used_rules_sumscore/used_rules_amount if used_rules_amount > 0 else 1.0 #AIRIS confidence
    #but if the certaintly predicted world has higher value, then set prediction score to the best it can be
    if (newworld[VALUES][0] == 1 and score == 1.0)  or (customGoal and customGoal(newworld)):
        score = float('-inf')
    #while if the certaintly predicted world has lower value, set prediction score to the worst it can be
    if newworld[VALUES][0] == -1 and score == 1.0:
        score = float('inf')
    return newworld, score, age, newworld[VALUES]

def _MatchHypotheses(FocusSet, oldworld, action, rules):
    positionscores = dict([])
    highesthighscore = 0.0
    AttendPositions = set([])
    for y in range(height):
        for x in range(width):
            if oldworld[BOARD][y][x] in FocusSet:
                AttendPositions.add((y,x))
                for rule in rules:
                    (precondition, consequence) = rule
                    action_score_and_preconditions = list(precondition)
                    for (y_rel, x_rel, requiredstate) in action_score_and_preconditions[2:]:
                        AttendPositions.add((y+y_rel, x+x_rel))
    for y in range(height):
        for x in range(width):
            if (y,x) not in AttendPositions:
                continue
            scores = dict([])
            positionscores[(y,x)] = scores
            highscore = 0.0
            highscorerule = None
            for rule in rules:
                (precondition, consequence) = rule
                action_score_and_preconditions = list(precondition)
                values = action_score_and_preconditions[1]
                if action_score_and_preconditions[0] == action:
                    scores[rule] = 0.0
                else:
                    continue
                CONTINUE = False
                for i in range(len(values)):
                    if values[i] != oldworld[VALUES][i+1]:
                        CONTINUE = True
                if CONTINUE:
                    continue
                for (y_rel, x_rel, requiredstate) in action_score_and_preconditions[2:]:
                    if y+y_rel >= height or y+y_rel < 0 or x+x_rel >= width or x+x_rel < 0:
                        CONTINUE = True
                        break
                    if oldworld[BOARD][y+y_rel][x+x_rel] == requiredstate:
                        scores[rule] += 1.0
                if CONTINUE:
                    continue
                scores[rule] /= (len(precondition)-2)
                if scores[rule] > 0.0 and (scores[rule] > highscore or (scores[rule] == highscore and highscorerule is not None and len(rule[0]) > len(highscorerule[0]))):
                    highscore = scores.get(rule, 0.0)
                    highscorerule = rule
            positionscores[(y,x)] = (scores, highscore, highscorerule)
            if highscore > highesthighscore:
                highesthighscore = highscore
    return (positionscores, highesthighscore)

def _RuleApplicable(scores, highscore, highesthighscore, rule):
    if highscore > 0.0 and scores.get(rule, 0.0) == highesthighscore:
        return True
    return False

"""
 * The MIT License
 *
 * Copyright (c) 2024 Patrick Hammer, Peter Isaev
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 * """

def Hypothesis_TruthValue(wpn):
    (wp, wn) = wpn
    frequency = wp / (wp + wn)
    confidende = (wp + wn) / (wp + wn + 1)
    return (frequency, confidende)

def Hypothesis_TruthExpectation(tv):
    (f, c) = tv
    return (c * (f - 0.5) + 0.5)

def Hypothesis_Choice(RuleEvidence, rule1, rule2):
    T1 = Hypothesis_TruthValue(RuleEvidence[rule1])
    T2 = Hypothesis_TruthValue(RuleEvidence[rule2])
    if Hypothesis_TruthExpectation(T1) > Hypothesis_TruthExpectation(T2):
        return rule1
    return rule2

def _AddEvidence(RuleEvidence, rule, positive, w_max = 20):
    if rule not in RuleEvidence:
        RuleEvidence[rule] = (0, 0)
    (wp, wn) = RuleEvidence[rule]
    if positive:
        if wp + wn <= w_max:
            RuleEvidence[rule] = (wp+1, wn)
        else:
            RuleEvidence[rule] = (wp, max(0, wn-1))
    else:
        if wp + wn <= w_max:
            RuleEvidence[rule] = (wp, wn+1)
        else:
            RuleEvidence[rule] = (max(0, wp-1), wn)
    return RuleEvidence
