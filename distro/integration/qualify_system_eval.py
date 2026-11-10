"""Resolve headless/COSMIC NixOS options without building or host activation."""
import argparse,json,os,subprocess
from pathlib import Path

def qualify(repository,base,source,output,live_image=False):
 repository,base,source,output=map(lambda x:Path(x).resolve(),(repository,base,source,output));output.mkdir(mode=0o700)
 lock=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text());rows=[]
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
 subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','roko-evaluation-fixture-do-not-deploy','-f',str(output/'fixture-key')],check=True,timeout=10)
 public=(output/'fixture-key.pub').read_text().strip()
 definition='live-image-eval.nix' if live_image else 'system-eval.nix'
 for mode in ('unprovisioned','headless','cosmic'):
  expr='let s=import (builtins.toPath '+json.dumps(str(repository/'distro/nix'/definition))+') { nixpkgsSource=builtins.toPath '+json.dumps(str(source))+'; expectedSourceNarHash='+json.dumps(lock['source_nar_hash'])+'; enableCosmic='+('true' if mode=='cosmic' else 'false')+'; adminPublicKey='+('null' if mode=='unprovisioned' else json.dumps(public))+'; }; c=s.config; in { failedAssertions=map (a: a.message) (builtins.filter (a: !a.assertion) c.assertions); cosmic=c.services.desktopManager.cosmic.enable; greeter=c.services.displayManager.cosmic-greeter.enable; rootPassword=c.users.users.root.hashedPassword; userPassword=c.users.users.roko.hashedPassword; mutableUsers=c.users.mutableUsers; sshEnabled=c.services.openssh.enable; sudoEnabled=c.security.sudo.enable; userNormal=c.users.users.roko.isNormalUser; canTouchEfi=c.boot.loader.efi.canTouchEfiVariables; packageManager="nix"; packageManagerEnabled=c.nix.enable; rootDevice=c.fileSystems."/".device; stateDevice=c.fileSystems."/home".device; scope=builtins.fromJSON c.environment.etc."roko/evaluation-scope.json".text; }'
  if live_image:
   expr=expr.replace('rootDevice=c.fileSystems."/".device; stateDevice=c.fileSystems."/home".device;', 'rootFs=c.fileSystems."/".fsType; rootDevice=c.fileSystems."/".device; autoLogin=c.services.displayManager.autoLogin.enable; gettyAutoLogin=c.services.getty.autologinUser; efi=c.isoImage.makeEfiBootable; bios=c.isoImage.makeBiosBootable; volume=c.isoImage.volumeID; liveScope=builtins.fromJSON c.environment.etc."roko/live-scope.json".text;')
  path=output/(mode+'.nix');path.write_text(expr)
  r=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],capture_output=True,text=True,env=env,timeout=120)
  (output/(mode+'.stdout')).write_text(r.stdout);(output/(mode+'.stderr')).write_text(r.stderr)
  value=json.loads(r.stdout) if not r.returncode else None
  assertion_gate=(len(value['failedAssertions'])==1 and 'Neither the root account' in value['failedAssertions'][0]) if value and mode=='unprovisioned' else value and not value['failedAssertions']
  passed=r.returncode==0 and assertion_gate and value['cosmic']==(mode=='cosmic') and value['greeter']==(mode=='cosmic') and value['packageManagerEnabled'] and value['userNormal'] and value['userPassword']=='!' and not value['mutableUsers'] and not value['sshEnabled'] and not value['sudoEnabled'] and not value['canTouchEfi'] and value['rootPassword']=='!'
  if live_image and passed:passed=value['rootFs']=='tmpfs' and not value['autoLogin'] and value['gettyAutoLogin'] is None and value['efi'] and value['bios']
  rows.append({'mode':mode,'returncode':r.returncode,'passed':passed,'evaluation':value})
 report={'passed':all(r['passed'] for r in rows),'evaluations':rows,'source_pin':lock,'import_from_derivation_allowed':False,'build_completed':False,'image_produced':False,'vm_booted':False,'host_activation':False,'live_image_definition':live_image,'scope':'module/option/assertion evaluation only; not system closure realization','credential_scope':'fresh local fixture SSH key, not a deployment credential; private key excluded from receipts'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('output');p.add_argument('--live-image',action='store_true');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.output,a.live_image);print(json.dumps({'passed':r['passed'],'modes':r['evaluations']}));raise SystemExit(0 if r['passed'] else 1)
