#!/usr/bin/env python3
"""Explicit legacy-v2 comparison. Legacy source is used for testing only.

Each adapter runs in a fresh subprocess. Neither exposes an execution path here.
"""
import argparse,json,os,subprocess,sys
from pathlib import Path
WORKER=r'''
import importlib,json,sys
sys.path.insert(0,sys.argv[1]);m=importlib.import_module(sys.argv[2]);r=json.load(sys.stdin)
try:
 raw=m.plan_single(r['name'],r['path'],r['snapshot']);doc=json.loads(raw)
 print(json.dumps({'accepted':True,'desired':doc['plan']['desired'],'operations':doc['plan']['operations'],'count':m.operation_count(raw),'path':m.planned_path(raw,r['name']),'has_package':m.has_planned_package(raw,r['name'],r['path']),'authority':m.authorizes_actions(raw),'executed':doc['package_changes_executed'],'live':doc['live_nix_observed'],'schema':doc['schema'],'complete_plan':doc['plan']}))
except (ValueError,TypeError,KeyError,getattr(m,'Error',ValueError)) as e:print(json.dumps({'accepted':False,'error_type':type(e).__name__}))
'''
def qualify(root,output):
 adapters=Path(root)/'omega-baseline/adapters';output=Path(output);output.mkdir(mode=0o700)
 a='/nix/store/'+'0'*32+'-fixture-a';b='/nix/store/'+'1'*32+'-fixture-b'
 def request(packages,**extra):return {'name':'hello','path':a,'snapshot':json.dumps({'packages':packages,'revision':'fixture-1','source':'disposable-parity'}),**extra}
 cases={'empty':request({}),'unchanged':request({'hello':a}),'replacement':request({'hello':b}),'remove-unrequested':request({'extra':b}),'replacement-and-removal':request({'hello':b,'extra':b}),'ordering-difference':request({'hello':b,'zeta':b}),'unicode-provenance':request({},snapshot=json.dumps({'packages':{},'revision':'époque-1','source':'fixture-λ'})),'invalid-output':request({},path='/bin/sh'),'invalid-name':request({},name='hello) (activate'),'duplicate-snapshot-key':request({},snapshot='{"packages":{},"packages":{},"revision":"1","source":"fixture"}'),'missing-provenance':request({},snapshot='{"packages":{},"revision":"1"}'),'invalid-observed-output':request({'hello':'/bin/sh'})}
 rows=[]
 for name,req in cases.items():
  results=[]
  for module in ('package_planning','package_planning_v2'):
   p=subprocess.run([sys.executable,'-B','-c',WORKER,str(adapters),module],input=json.dumps(req),capture_output=True,text=True,timeout=10,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   if p.returncode:raise RuntimeError(p.stderr)
   results.append(json.loads(p.stdout))
  old,new=results
  equal=old['accepted']==new['accepted']
  if equal and old['accepted']:
   fields=('desired','count','path','has_package','authority','executed','live','complete_plan')
   equal=all(old[k]==new[k] for k in fields)
   equal=equal and sorted(old['operations'],key=lambda x:json.dumps(x,sort_keys=True))==sorted(new['operations'],key=lambda x:json.dumps(x,sort_keys=True))
   equal=equal and not new['authority'] and not new['live'] and new['executed']==0
  rows.append({'case':name,'passed':equal,'operation_order_equal': old.get('operations')==new.get('operations'),'legacy':old,'successor':new})
 report={'passed':all(r['passed'] for r in rows),'cases':rows,'scope':'active scalar snapshot bridge helpers and complete inner plan equality, including order and checksum; outer report schema/mode intentionally versioned; no general source-parser parity','package_mutations':0,'live_nix_observation':False,'license_clearance':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.output);print(json.dumps({'passed':r['passed'],'cases':len(r['cases'])}));sys.exit(0 if r['passed'] else 1)
