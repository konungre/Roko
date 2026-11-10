"""Offline closure preflight and local-cache export, with no build/repair flags.

Input roots are reviewed derivation paths. Export happens only after path-info
and ordinary store verification succeed. Trust/signature checks are not disabled.
"""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path

def qualify(base,roots,output):
 base,roots,output=map(lambda x:Path(x).resolve(),(base,roots,output));output.mkdir(mode=0o700)
 requested=json.loads(roots.read_text())
 if set(requested)!={'scope','roots'} or requested['scope'] not in ('image','fixture'):raise ValueError('explicit root scope required')
 if not 1<=len(requested['roots'])<=8:raise ValueError('root bound')
 for item in requested['roots']:
  if not isinstance(item,dict) or set(item)!={'label','derivation'}:raise ValueError('root fields')
  if not isinstance(item['label'],str) or not 1<=len(item['label'])<=128:raise ValueError('root label')
  if not isinstance(item['derivation'],str):raise ValueError('derivation path string required')
  path=Path(item['derivation'])
  if path.parent!=base/'direct-store' or not re.fullmatch('[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._=-]+\.drv',path.name):raise ValueError('exact local derivation required')
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline']
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')};rows=[]
 def run(label,args):
  r=subprocess.run(prefix+args,env=env,capture_output=True,text=True,timeout=120)
  (output/(label+'.stdout')).write_text(r.stdout);(output/(label+'.stderr')).write_text(r.stderr);return r
 for index,item in enumerate(requested['roots']):
  r=run(str(index)+'-derivation',['derivation','show',item['derivation']])
  if r.returncode:rows.append({'label':item['label'],'available':False,'reason':'derivation observation failed','returncode':r.returncode});continue
  d=json.loads(r.stdout)
  if len(d)!=1:raise ValueError('one derivation per root required')
  path=next(iter(d.values()))['outputs']['out']['path']
  r=run(str(index)+'-preflight',['path-info','--recursive','--json',path])
  rows.append({'label':item['label'],'derivation':item['derivation'],'output':path,'available':r.returncode==0,'preflight_returncode':r.returncode,'output_exists':Path(path).exists()})
 available=all(row['available'] and row.get('output_exists') for row in rows)
 verified=False;exported=False
 if available:
  paths=sorted(set(row['output'] for row in rows))
  verification=run('verification',['store','verify','--recursive',*paths]);verified=verification.returncode==0
  if verified:
   cache=output/'cache'
   exported=run('export',['copy','--to',cache.as_uri(),*paths]).returncode==0
 cache_files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (output/'cache').rglob('*') if p.is_file()} if (output/'cache').exists() else {}
 report={'scope':requested['scope'],'roots':rows,'closure_available':available,'verification_attempted':available,'export_attempted':available and verified,'ordinary_store_verification_passed':verified,'local_cache_exported':exported,'cache_file_hashes':cache_files,'build_requested':False,'repair_requested':False,'trust_checks_disabled':False,'host_activation':False,'sandbox_retried':False,'image_built':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('roots');p.add_argument('output');a=p.parse_args();r=qualify(a.base,a.roots,a.output);print(json.dumps(r));raise SystemExit(0 if r['local_cache_exported'] else 2)
