"""Independent read-only scalar snapshot planner. No omega_pm imports or executor.

This opt-in successor consumes validated JSON snapshots, not MeTTa source code.
The legacy adapter remains unchanged until consumers explicitly adopt v2.
"""
import json,re

def _packages(value):
 if not isinstance(value,dict):raise ValueError('package object required')
 for key,path in value.items():
  if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}',key):raise ValueError('name')
  if not isinstance(path,str) or not re.fullmatch('/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+',path):raise ValueError('store output')
 return value

def plan_single(name,path,snapshot_json):
 requested=_packages({name:path})
 if not isinstance(snapshot_json,str) or len(snapshot_json.encode())>1024*1024:raise ValueError('bounded snapshot text required')
 def unique(pairs):
  result={}
  for key,value in pairs:
   if key in result:raise ValueError('duplicate snapshot field')
   result[key]=value
  return result
 snapshot=json.loads(snapshot_json,object_pairs_hook=unique)
 if not isinstance(snapshot,dict) or set(snapshot)!={'packages','revision','source'}:raise ValueError('snapshot fields')
 for field in ('revision','source'):
  if not isinstance(snapshot[field],str) or not 1<=len(snapshot[field])<=4096:raise ValueError('snapshot provenance')
 old=_packages(snapshot['packages']);changes=[]
 for key in sorted(old):
  if requested.get(key)!=old[key]:changes.append({'op':'remove','name':key,'path':old[key]})
 for key in sorted(requested):
  if old.get(key)!=requested[key]:changes.append({'op':'install','name':key,'path':requested[key]})
 return json.dumps({'schema':2,'mode':'read-only-snapshot-planning-v2','authorizes_actions':False,'package_changes_executed':0,'live_nix_observed':False,'plan':{'desired':requested,'operations':changes,'before':snapshot},'limitations':'Caller-supplied historical snapshot only; not executable or observed Nix state.'},sort_keys=True)

def operation_count(report):return len(json.loads(report)['plan']['operations'])
def planned_path(report,name):return json.loads(report)['plan']['desired'][name]
def authorizes_actions(report):return json.loads(report)['authorizes_actions']
def has_planned_package(report,name,path):return json.loads(report)['plan']['desired'].get(name)==path
