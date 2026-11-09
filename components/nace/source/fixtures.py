"""Fixed synthetic cases only. No user state, environments, goals or actions."""
from copy import deepcopy

def rule(index=0, *, conditions=None, result='f', values=None, evidence=None, action='right', inventory=0):
    return {'id':'r'+str(index),'action':action,'inventory':inventory,
            'conditions':conditions or [[0,0,'x']], 'result':result,
            'values':[0,0] if values is None else values,
            'evidence':[1,0] if evidence is None else evidence}

def base():
    return {'board':[['.','.','.'],['.','x','.'],['.','.','.']],
            'values':[0,0],'times':[[0,0,0],[0,2,0],[0,0,0]],'now':5,
            'focus':[['x',2]],'action':'right','rules':[rule()], 'updates':[]}

def cases():
    rows=[]
    def add(name,change):
        x=base();change(x);rows.append({'id':name,'request':x})
    add('unattended_no_change',lambda x:x.update(focus=[]))
    add('exact_reward',lambda x:x['rules'][0].update(values=[1,0]))
    add('exact_penalty',lambda x:x['rules'][0].update(values=[-1,0]))
    add('partial_match',lambda x:x['rules'][0].update(conditions=[[0,0,'x'],[0,1,'k']]))
    add('inventory_mismatch',lambda x:x.update(values=[0,1]))
    add('action_mismatch',lambda x:x.update(action='left'))
    add('stronger_evidence',lambda x:x.update(rules=[rule(evidence=[3,1]),rule(1,result='o',evidence=[1,3])]))
    add('evidence_reversal',lambda x:x.update(rules=[rule(evidence=[3,1]),rule(1,result='o',evidence=[1,3])],
        updates=[['r0',False],['r0',False],['r1',True],['r1',True],['r1',True],['r1',True]]))
    add('saturated_evidence',lambda x:x.update(rules=[rule(evidence=[20,0])],updates=[['r0',True],['r0',False]]))
    add('equal_truth_second_wins',lambda x:x.update(rules=[rule(evidence=[1,1]),rule(1,result='o',evidence=[1,1])]))
    add('more_conditions_match_tie',lambda x:x.update(rules=[rule(),rule(1,conditions=[[0,0,'x'],[0,1,'.']],result='k')]))
    def suppression(x):
        x['board'][0][0]='k';x['focus'].append(['k',1]);
        x['rules']=[rule(conditions=[[0,0,'x'],[0,1,'o']],result='f'),rule(1,conditions=[[0,0,'k']],result='u')]
    add('global_best_suppresses_partial',suppression)
    return deepcopy(rows)
