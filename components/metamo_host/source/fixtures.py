"""Fixed non-sensitive local proposals. No external actions are represented."""
from copy import deepcopy

def candidate(name, corrs=None, risk=0.1, delta=None):
    return dict(id=name, correlations=corrs or [0.0]*8, risk=risk, delta_goals=delta or [0.0]*8)

def request(name, candidates, goals=None, modulators=None):
    return dict(version=1, request_id=name, operation='rank_proposals',
                state=dict(goals=goals or [0.5]*8, modulators=modulators or [0.5]*6), candidates=candidates)

def cases():
    common=[0,0,0.2,0.2,0.2,0.2,0.2,0.2]
    tie=candidate('first',common)
    return [
        ('upstream-score', request('upstream-score', [candidate('act1',[0,0,0.25,0.5,0.3,0.1,0.2,0.15],0.1,[0,0,0.05,0.1,0.05,0,0,0])]), 'act1'),
        ('upstream-choice', request('upstream-choice', [candidate('act1',[0,0,0.1,0.1,0.1,0.1,0.1,0.1],0.1,[0,0,0.01,0.01,0.01,0,0,0]),candidate('act2',[0,0,0.5,0.5,0.5,0.5,0.5,0.5],0.05,[0,0,0.05,0.05,0.05,0,0,0])]), 'act2'),
        ('upstream-conflict', request('upstream-conflict', [candidate('conflict_act',[0,0,0,0.8,0,0,-0.8,0],0.01,[0,0,0,0.08,0,0,-0.08,0]),candidate('safe_act',[0,0,0,0.1,0,0,0.8,0],0.01,[0,0,0,0.01,0,0,0.08,0])]), 'safe_act'),
        ('risk-preference', request('risk-preference', [candidate('risky',common,0.9),candidate('low-risk',common,0.01)],goals=[0.9]*8,modulators=[0.9]*6), 'low-risk'),
        ('growth-preference', request('growth-preference', [candidate('no-shift',common),candidate('growth-shift',common,delta=[0,0,0,0.1,0.1,0.1,0,0])]), 'growth-shift'),
        ('first-tie', request('first-tie', [tie,dict(deepcopy(tie),id='second')]), 'first'),
        ('reverse-tie', request('reverse-tie', [dict(deepcopy(tie),id='second'),tie]), 'second'),
        ('capacity-eight', request('capacity-eight', [candidate('proposal-%d'%i,[0,0]+[round(i*0.1,6)]*6) for i in range(8)]), 'proposal-7')]
