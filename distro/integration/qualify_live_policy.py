"""Evaluate explicit live firmware/network/access policies, never activate them."""
import argparse,hashlib,json,os,secrets,subprocess
from pathlib import Path

def qualify(repository,base,source,output):
 repository,base,source,output=map(lambda x:Path(x).resolve(),(repository,base,source,output));output.mkdir(mode=0o700)
 subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','local-policy-fixture-do-not-deploy','-f',str(output/'fixture-key')],check=True,timeout=10)
 public=(output/'fixture-key.pub').read_text().strip()
 credential=subprocess.run(['openssl','passwd','-6','-stdin'],input=secrets.token_urlsafe(48)+'\n',text=True,capture_output=True,check=True,timeout=10).stdout.strip()
 lock=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text())
 common={'nixpkgsSource':str(source),'expectedSourceNarHash':lock['source_nar_hash'],'enableCosmic':True,'adminPublicKey':public}
 cases=[('offline-locked',{},False),('console-password',{'adminAccess':'console-password','adminPasswordHash':credential},False),('managed-key-console',{'networkPolicy':'managed','adminAccess':'ssh-key-and-password','adminPasswordHash':credential},False),('redistributable-firmware',{'firmwarePolicy':'redistributable'},False),('missing-console-credential',{'adminAccess':'console-password'},True),('ssh-offline',{'adminAccess':'ssh-key-and-password','adminPasswordHash':credential},True),('plaintext-credential',{'adminAccess':'console-password','adminPasswordHash':'not-a-hash'},True),('missing-ssh-key',{'networkPolicy':'managed','adminAccess':'ssh-key-and-password','adminPasswordHash':credential,'adminPublicKey':None},True),('malformed-ssh-key',{'networkPolicy':'managed','adminAccess':'ssh-key-and-password','adminPasswordHash':credential,'adminPublicKey':'not-a-public-key'},True),('unrestricted-firmware',{'firmwarePolicy':'all'},True),('unknown-network',{'networkPolicy':'automatic'},True)]
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 fields='{ failedAssertions=map (a: a.message) (builtins.filter (a: !a.assertion) c.assertions); networkManager=c.networking.networkmanager.enable; firmware=c.hardware.enableRedistributableFirmware; allFirmware=c.hardware.enableAllFirmware; firmwareDerivation=c.hardware.firmware.drvPath; userPasswordSet=c.users.users.roko.hashedPassword!="!"; rootLocked=c.users.users.root.hashedPassword=="!"; ssh=c.services.openssh.enable; rootSsh=c.services.openssh.settings.PermitRootLogin; sshMethods=c.services.openssh.settings.AuthenticationMethods; sshUsers=c.services.openssh.settings.AllowUsers; emptyPasswords=c.services.openssh.settings.PermitEmptyPasswords; passwordSsh=c.services.openssh.settings.PasswordAuthentication; interactiveSsh=c.services.openssh.settings.KbdInteractiveAuthentication; sudo=c.security.sudo.enable; sudoPassword=c.security.sudo.wheelNeedsPassword; autoLogin=c.services.displayManager.autoLogin.enable; autoUpgrade=c.system.autoUpgrade.enable; automaticGc=c.nix.gc.automatic; automaticOptimise=c.nix.optimise.automatic; substituters=c.nix.settings.substituters; flakeRegistry=c.nix.settings.flake-registry or null; channel=c.nix.channel.enable; nixPath=c.nix.nixPath; registryNames=builtins.attrNames c.nix.registry; waitOnline=c.systemd.network.wait-online.enable; nmWaitEnabled=c.systemd.services.NetworkManager-wait-online.enable or null; firstBoot=builtins.fromJSON c.environment.etc."roko/first-boot.json".text; }'
 rows=[]
 for name,options,reject in cases:
  parameters={**common,**options};encoded=json.dumps(json.dumps(parameters)).replace('${','\\${')
  expr='let s=import (builtins.toPath '+json.dumps(str(repository/'distro/nix/live-image-eval.nix'))+') (builtins.fromJSON '+encoded+'); c=s.config; in '+fields
  path=output/(name+'.nix');path.write_text(expr)
  r=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')},capture_output=True,text=True,timeout=120)
  # Error context can echo a fixture credential embedded in the local expression.
  (output/(name+'.stderr')).write_text(r.stderr.replace(credential,'<fixture-hash-redacted>'))
  value=json.loads(r.stdout) if r.returncode==0 else None
  if reject:passed=r.returncode!=0 and 'assertion' in r.stderr.lower()
  else:
   passed=r.returncode==0 and not value['failedAssertions'] and value['rootLocked'] and not value['allFirmware'] and not value['autoLogin'] and value['rootSsh']=='no' and not value['passwordSsh'] and not value['interactiveSsh'] and value['sudoPassword'] and value['sshMethods']=='publickey' and value['sshUsers']==['roko'] and not value['emptyPasswords'] and not value['autoUpgrade'] and not value['automaticGc'] and not value['automaticOptimise']
   if passed:passed=value['userPasswordSet']==(options.get('adminAccess','locked')!='locked') and value['networkManager']==(options.get('networkPolicy')=='managed') and value['ssh']==(options.get('adminAccess')=='ssh-key-and-password') and value['sudo']==(options.get('adminAccess','locked')!='locked') and value['firmware']==(options.get('firmwarePolicy')=='redistributable')
  if passed and not reject and options.get('networkPolicy','offline')=='offline':passed=not value['substituters'] and value['flakeRegistry']=='' and not value['channel'] and not value['nixPath'] and not value['registryNames'] and not value['waitOnline'] and value['nmWaitEnabled'] is False and value['firstBoot']['offlineRequested']
  rows.append({'case':name,'expected_rejection':reject,'returncode':r.returncode,'passed':passed,'evaluation':value})
 report={'passed':all(r['passed'] for r in rows),'cases':rows,'host_activation':False,'build_completed':False,'credential_scope':'ephemeral local fixture; no cleartext/hash/private key committed','firmware_license_audit_completed':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.output);print(json.dumps({'passed':r['passed'],'cases':[{k:x[k] for k in ('case','returncode','passed')} for x in r['cases']]}));raise SystemExit(0 if r['passed'] else 1)
