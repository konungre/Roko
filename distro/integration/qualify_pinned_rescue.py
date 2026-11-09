"""Evaluate pinned rescue inputs offline; never build or activate a generation."""
import argparse,base64,hashlib,json,os,subprocess
from pathlib import Path

def qualify(repository,base,source,output):
 repository,base,source,output=map(lambda x:Path(x).resolve(),(repository,base,source,output));output.mkdir(mode=0o700)
 lock=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text());boot=repository/'omega-baseline/boot'
 hashes={k:hashlib.sha256((boot/n).read_bytes()).hexdigest() for k,n in [('init','init.c'),('builder','build.py')]}
 expression='let d=import (builtins.toPath '+json.dumps(str(repository/'distro/nix/rescue-pinned.nix'))+') { nixpkgsSource=builtins.toPath '+json.dumps(str(source))+'; expectedSourceNarHash='+json.dumps(lock['source_nar_hash'])+'; sourceHashes={ init="'+hashes['init']+'"; builder="'+hashes['builder']+'"; }; }; in { derivationPath=d.drvPath; outputPath=d.outPath; platform=d.system; }'
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline']
 rows=[]
 for name,expr in [('pinned',expression),('wrong-pin',expression.replace(lock['source_nar_hash'],'sha256-'+base64.b64encode(bytes(32)).decode()))]:
  path=output/(name+'.nix');path.write_text(expr)
  r=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],env=env,capture_output=True,text=True,timeout=120)
  (output/(name+'.stdout')).write_text(r.stdout);(output/(name+'.stderr')).write_text(r.stderr)
  rows.append({'mode':name,'returncode':r.returncode,'result':json.loads(r.stdout) if r.returncode==0 else None})
 passed=rows[0]['returncode']==0 and rows[1]['returncode']!=0 and 'mismatch' in (output/'wrong-pin.stderr').read_text()
 report={'passed':passed,'source_pin':lock,'source_hashes':hashes,'evaluations':rows,'stage':'resolved-only','build_completed':False,'sandbox_isolation_proven':False,'host_activation':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.output);print(json.dumps({'passed':r['passed'],'stage':r['stage']}));raise SystemExit(0 if r['passed'] else 1)
