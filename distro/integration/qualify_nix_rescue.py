"""Real Nix bootstrap rescue build and forced rebuild in a workspace store."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def qualify(repository,base,output):
 repository,base,output=map(lambda x:Path(x).resolve(),(repository,base,output));output.mkdir(mode=0o700)
 boot=repository/'omega-baseline/boot';hashes={'init':sha(boot/'init.c'),'builder':sha(boot/'build.py')}
 definition=repository/'distro/nix/rescue.nix'
 expression='import (builtins.toPath '+json.dumps(str(definition))+') { bootstrapPython='+json.dumps(sys.executable)+'; bootstrapPath="/usr/bin:/bin"; sourceHashes={ init="'+hashes['init']+'"; builder="'+hashes['builder']+'"; }; }'
 (output/'build.nix').write_text(expression)
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','build-users-group','','--option','sandbox','false']
 rows=[];before=None
 for mode in ('build','rebuild'):
  cmd=prefix+['build','--impure','--file',str(output/'build.nix'),'--no-link','--json']+(['--rebuild'] if mode=='rebuild' else [])
  r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
  (output/(mode+'.stdout')).write_text(r.stdout);(output/(mode+'.stderr')).write_text(r.stderr)
  rows.append({'mode':mode,'returncode':r.returncode})
  if r.returncode:break
  result=json.loads(r.stdout)[0];root=Path(result['outputs']['out'])
  assets={n:sha(root/n) for n in ('init','roko-initramfs.cpio.gz','build-manifest.json')}
  if before is None:before=assets
  rows[-1].update({'derivation':result['drvPath'],'output':str(root),'assets':assets,'matches_first':assets==before})
 bad_expression=expression.replace(hashes['init'],'0'*64)
 negative=subprocess.run(prefix+['eval','--impure','--raw','--expr','('+bad_expression+').drvPath'],env=env,capture_output=True,text=True,timeout=30)
 (output/'wrong-source.stderr').write_text(negative.stderr)
 source_mismatch_rejected=negative.returncode!=0 and 'assertion' in negative.stderr.lower()
 passed=source_mismatch_rejected and len(rows)==2 and all(r['returncode']==0 and r.get('matches_first') for r in rows)
 report={'passed':passed,'builds':rows,'source_mismatch_rejected':source_mismatch_rejected,'source_hashes':hashes,'definition_sha256':sha(definition),'bootstrap_python':sys.executable,'bootstrap_python_sha256':sha(sys.executable),'host_gcc_sha256':sha('/usr/bin/gcc'),'host_toolchain_closure_pinned':False,'sandbox':False,'host_activation':False,'cosmic_included':False,'model_included':False,'kernel_included':False,'scope':'Nix-managed local bootstrap rescue derivation with forced rebuild; not NixOS or hermetic OS image'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.output);print(json.dumps({'passed':r['passed'],'builds':r['builds']}));sys.exit(0 if r['passed'] else 1)
