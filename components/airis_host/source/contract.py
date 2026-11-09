"""Strict inert transition data. This oracle validates, never supplies AIRIS output."""
import hashlib
import json
import re
MAX_REQUEST=8192
MAX_RESPONSE=49152

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('Duplicate JSON key')
  d[k]=v
 return d
def decode(raw,cap):
 if type(raw) is not bytes or not 1<=len(raw)<=cap:raise ValueError('Packet cap')
 try:return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
 except (UnicodeError,RecursionError) as e:raise ValueError('Encoding/nesting') from e
def integer(v,lo,hi):
 if type(v) is not int or not lo<=v<=hi:raise ValueError('Bounded integer required')
 return v
def ident(v):
 if type(v) is not str or re.fullmatch('[a-z][a-z0-9_]{0,31}',v,re.ASCII) is None:raise ValueError('Identifier')
 return v
def observation(identifier,source,before,action,after):
 v={'id':identifier,'source':source,'before':before,'action':action,'after':after};return dict(v,sha256=digest(v))
def validate_request(v):
 if type(v) is not dict or set(v)!={'version','operation','task_id','revision','training','query'}:raise ValueError('Request schema')
 integer(v['version'],1,1);integer(v['revision'],1,2**53-1);ident(v['task_id'])
 if v['operation']!='learn-scalar-transition':raise ValueError('Operation')
 integer(v['query'],1,64)
 rows=v['training']
 if type(rows) is not list or len(rows)!=4:raise ValueError('Four observations required')
 for r in rows:
  if type(r) is not dict or set(r)!={'id','source','before','action','after','sha256'}:raise ValueError('Observation schema')
  ident(r['id']);integer(r['before'],2,32);integer(r['after'],1,34)
  if type(r['source']) is not str or not 1<=len(r['source'].encode())<=256:raise ValueError('Source cap')
  if r['action'] not in ('step','hold') or type(r['action']) is not str:raise ValueError('Action token')
  if r['sha256']!=digest({k:x for k,x in r.items() if k!='sha256'}):raise ValueError('Observation digest')
 if len({r['id'] for r in rows})!=4:raise ValueError('Evidence reuse')
 if [r['action'] for r in rows]!=['step','step','hold','hold']:raise ValueError('Fixed training order')
 a,b,c,d=rows
 if a['before']==b['before'] or c['before']!=a['before'] or d['before']!=b['before']:raise ValueError('Paired starting states')
 delta=a['after']-a['before']
 if delta not in (-2,-1,1,2) or b['after']-b['before']!=delta or c['after']!=c['before'] or d['after']!=d['before']:raise ValueError('Restricted deterministic scalar experiment')
 if v['query'] in {r['before'] for r in rows} or not 1<=v['query']+delta<=66:raise ValueError('Held-out query')
 return decode(canonical(v),MAX_REQUEST)
def parse_request(raw):return validate_request(decode(raw,MAX_REQUEST))
def expected(v):
 v=validate_request(v);q=v['query'];delta=v['training'][0]['after']-v['training'][0]['before']
 return {'learned':{'step':q+delta,'hold':q},'empty':{'step':q,'hold':q},'restored':{'step':q+delta,'hold':q}}
def response(v,native):
 v=validate_request(v)
 if type(native) is not dict or set(native)!={'predictions','learned_rules','rule_updates','steps','knowledge_snapshot_sha256','max_graph_nodes','max_knowledge_keys','upstream_line_events','planner_calls'}:raise ValueError('Native schema')
 if canonical(native['predictions'])!=canonical(expected(v)):raise ValueError('Actual AIRIS predictions disagree with independent transition oracle')
 integer(native['learned_rules'],2,2);integer(native['rule_updates'],2,2);integer(native['steps'],4,4)
 integer(native['max_graph_nodes'],1,24);integer(native['max_knowledge_keys'],1,128);integer(native['upstream_line_events'],1,200000);integer(native['planner_calls'],0,0)
 if type(native['knowledge_snapshot_sha256']) is not str or re.fullmatch('[0-9a-f]{64}',native['knowledge_snapshot_sha256']) is None:raise ValueError('Snapshot digest')
 return {'version':1,'operation':v['operation'],'task_id':v['task_id'],'revision':v['revision'],'request_sha256':digest(v),'training':v['training'],'query':v['query'],'predictions':native['predictions'],'status':'synthetic-transition-fixture','evidence_ids':[r['id'] for r in v['training']],'authorizes_actions':False,'executed_external_actions':0,'persistent_state_changed':False,'general_causal_learning_established':False,'full_airis':False}
def validate_packet(packet,request):
 v=validate_request(request)
 if type(packet) is not dict or set(packet)!={'version','request','native','response','runtime','network_denial_observed','upstream_sha256'}:raise ValueError('Packet schema')
 if canonical(packet['version'])!=b'1' or canonical(packet['request'])!=canonical(v) or packet['network_denial_observed'] is not True:raise ValueError('Packet identity/network')
 result=response(v,packet['native'])
 if canonical(result)!=canonical(packet['response']):raise ValueError('Response/provenance/authority changed')
 return result
