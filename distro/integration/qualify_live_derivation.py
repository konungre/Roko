"""Resolve ISO/system identities from reviewed module evaluation expressions.

No build, copy, installation or activation command is issued. IFD stays disabled.
"""
import argparse,json,os,resource,subprocess
from pathlib import Path

def qualify(base,evaluations,output):
 base,evaluations,output=map(lambda x:Path(x).resolve(),(base,evaluations,output));output.mkdir(mode=0o700)
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 rows=[]
 def limits():
  resource.setrlimit(resource.RLIMIT_CORE,(0,0))
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 for mode in ('headless','cosmic','headless-repeat'):
  original=(evaluations/(mode.replace('-repeat','')+'.nix')).read_text()
  prefix_expr,separator,_=original.partition('; c=s.config; in ')
  if not separator:raise ValueError('expected reviewed module expression')
  expr=prefix_expr+'; c=s.config; in { imageDerivation=c.system.build.isoImage.drvPath; systemDerivation=c.system.build.toplevel.drvPath; imageRelativePath=c.image.filePath; }'
  path=output/(mode+'.nix');path.write_text(expr)
  try:
   r=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],env=env,capture_output=True,text=True,timeout=120,preexec_fn=limits)
   (output/(mode+'.stdout')).write_text(r.stdout);(output/(mode+'.stderr')).write_text(r.stderr)
   rows.append({'mode':mode,'returncode':r.returncode,'resolved':r.returncode==0,'identities':json.loads(r.stdout) if not r.returncode else None})
  except subprocess.TimeoutExpired as e:
   (output/(mode+'.stderr')).write_bytes(e.stderr or b'');rows.append({'mode':mode,'resolved':False,'reason':'120-second evaluation deadline'})
 stable=bool(rows[0].get('identities')) and rows[0].get('identities')==rows[2].get('identities')
 report={'identity_repeat_matches':stable,'all_resolved':stable and all(r['resolved'] for r in rows),'evaluations':rows,'import_from_derivation_allowed':False,'memory_limit_gib':4,'build_completed':False,'image_produced':False,'vm_booted':False,'host_activation':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('evaluations');p.add_argument('output');a=p.parse_args();r=qualify(a.base,a.evaluations,a.output);print(json.dumps(r));raise SystemExit(0 if r['all_resolved'] else 1)
