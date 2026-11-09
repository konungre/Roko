"""Exercise original AIRIS learning/prediction, never external action execution.

Controller injects a one-item replay action_plan, bypassing exploratory planning.
The original pre/post capture, create/update-rule, predict and snapshot methods run.
"""
import copy
import hashlib
import json
import math
import sys
from contract import validate_request

class Bounds:
 def __init__(self,upstream):self.upstream=str(upstream);self.lines=0;self.max_nodes=0;self.max_keys=0
 def trace(self,frame,event,arg):
  if frame.f_code.co_filename==self.upstream:
   if event=='call' and frame.f_code.co_name=='make_plan':raise RuntimeError('Planner execution forbidden in replay slice')
   if event=='line':
    self.lines+=1
    if self.lines>200000:raise RuntimeError('Upstream line budget')
  return self.trace
 def check(self,agent):
  self.max_nodes=max(self.max_nodes,len(agent.state_graph));self.max_keys=max(self.max_keys,len(agent.knowledge))
  if self.max_nodes>24 or self.max_keys>128:raise ValueError('AIRIS state growth cap')
  if len(agent.action_plan)>1:raise ValueError('Plan cap')

ACTIONS={'step':None,'hold':None}
def begin(agent,value,action,bounds):
 u={'meter':[value]};a=(action,None)
 # Original pre_capture creates the grounded graph node; a supplied replay plan
 # makes it return the prescribed observed action rather than invoking planner.
 h=agent.make_hash({},u,ACTIONS)
 agent.action_plan=[(a,h,0,None)]
 returned=json.loads(agent.pre_capture_input('{}',json.dumps(u),json.dumps(ACTIONS),'{}'))
 if returned!=[action,None]:raise ValueError('Replay action changed')
 predicted=agent.predict(a,agent.pre_capture_state)
 agent.prediction_state=predicted;agent.prediction_match=0
 bounds.check(agent)
 return predicted

def predicted_value(agent,node):
 s=agent.state_graph[node]
 if s['s_input']!={} or s['actions']!=ACTIONS or type(s['u_input']) is not dict or set(s['u_input'])!={'meter'}:raise ValueError('Prediction shape')
 values=s['u_input']['meter']
 if type(values) is not list or len(values)!=1 or type(values[0]) not in (int,float) or not math.isfinite(values[0]):raise ValueError('Finite scalar prediction')
 return values[0]

def run(agent,request,bounds):
 v=validate_request(request)
 for row in v['training']:
  begin(agent,row['before'],row['action'],bounds)
  agent.post_capture_input('{}',json.dumps({'meter':[row['after']]}),json.dumps(ACTIONS))
  bounds.check(agent)
 snapshot=agent.get_knowledge()
 if type(snapshot) is not str or not 1<=len(snapshot.encode())<=32768:raise ValueError('Knowledge snapshot cap')
 rules=agent.knowledge.get('u-meter/outcome_ids',set());updates=agent.knowledge.get('action_updates',{})
 if type(rules) is not set or type(updates) is not dict:raise ValueError('Original learned state shape')
 learned_rules=len(rules);rule_updates=sum(updates.values());steps=agent.time_step
 saved=copy.deepcopy(agent.knowledge)
 predictions={}
 for mode in ('learned','empty','restored'):
  if mode=='empty':agent.knowledge={}
  if mode=='restored':
   agent.load_knowledge(snapshot)
   if agent.knowledge!=saved:raise ValueError('Original snapshot restoration changed knowledge')
  agent.state_graph={};agent.action_plan=[]
  values={}
  for action in ('step','hold'):
   node=begin(agent,v['query'],action,bounds);values[action]=predicted_value(agent,node)
  predictions[mode]=values
 return {'predictions':predictions,'learned_rules':learned_rules,'rule_updates':rule_updates,'steps':steps,'knowledge_snapshot_sha256':hashlib.sha256(snapshot.encode()).hexdigest(),'max_graph_nodes':bounds.max_nodes,'max_knowledge_keys':bounds.max_keys,'upstream_line_events':bounds.lines,'planner_calls':0}
