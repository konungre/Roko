"""Independent read-only scalar snapshot planner. No omega_pm imports or executor.

This opt-in successor consumes validated JSON snapshots, not MeTTa source code.
The legacy adapter remains unchanged until consumers explicitly adopt v2.
"""
import hashlib,json,re
from dataclasses import dataclass
Error = ValueError

def _packages(value):
 if not isinstance(value,dict):raise ValueError('package object required')
 for key,path in value.items():
  if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}',key):raise ValueError('name')
  if not isinstance(path,str) or not re.fullmatch('/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+',path):raise ValueError('store output')
 return value

def _object(source):
 if not isinstance(source,str) or len(source.encode())>1024*1024:raise ValueError('bounded JSON text required')
 def unique(pairs):
  result={}
  for key,value in pairs:
   if key in result:raise ValueError('duplicate JSON field')
   result[key]=value
  return result
 value=json.loads(source,object_pairs_hook=unique)
 if not isinstance(value,dict):raise ValueError('JSON object required')
 return value

@dataclass(frozen=True)
class _Snapshot:
 packages:dict
 revision:str
 def document(self):return {'packages':dict(self.packages),'revision':self.revision}

class SnapshotOnly:
 def __init__(self,source):
  self._value=_object(source)
  if set(self._value)!={'packages','revision','source'}:raise ValueError('snapshot fields')
  _packages(self._value['packages'])
  for field in ('revision','source'):
   if not isinstance(self._value[field],str) or not 1<=len(self._value[field])<=4096:raise ValueError('snapshot provenance')
  self.identity='snapshot-only:'+self._value['source']
 @property
 def snapshot(self):return self.observe()
 def observe(self):return _Snapshot(dict(self._value['packages']),self._value['revision'])

def plan_source(desired_source,snapshot_json):
 document=_object(desired_source)
 if set(document)!={'schema','packages'} or document['schema']!='roko-snapshot-desired-v2':raise ValueError('explicit desired JSON schema required; no MeTTa text evaluator')
 return _report(_packages(document['packages']),snapshot_json)

def plan_single(name,path,snapshot_json):
 return json.dumps(_report(_packages({name:path}),snapshot_json),sort_keys=True)

def _report(requested,snapshot_json):
 observed=SnapshotOnly(snapshot_json)
 snapshot={**observed.observe().document(),'source':observed._value['source']}
 old=_packages(snapshot['packages']);changes=[]
 for key in sorted(old):
  if requested.get(key)!=old[key]:changes.append({'op':'remove','name':key,'path':old[key]})
 for key in sorted(requested):
  if old.get(key)!=requested[key]:changes.append({'op':'install','name':key,'path':requested[key]})
 changes.sort(key=lambda item:(item['name'],0 if item['op']=='remove' else 1))
 plan={'schema':1,'backend':'snapshot-only:'+snapshot['source'],'before':{'packages':old,'revision':snapshot['revision']},'desired':requested,'operations':changes}
 plan['id']=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
 return {'schema':2,'mode':'read-only-snapshot-planning-v2','authorizes_actions':False,'package_changes_executed':0,'live_nix_observed':False,'plan':plan,'limitations':'Caller-supplied historical snapshot only; not executable or observed Nix state.'}

def operation_count(report):return len(json.loads(report)['plan']['operations'])
def planned_path(report,name):return json.loads(report)['plan']['desired'][name]
def authorizes_actions(report):return json.loads(report)['authorizes_actions']
def has_planned_package(report,name,path):return json.loads(report)['plan']['desired'].get(name)==path
