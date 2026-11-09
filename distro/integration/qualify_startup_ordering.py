"""Evaluate pinned boot ordering; no systemd startup, build or activation."""
import argparse,json,os,subprocess
from pathlib import Path
def qualify(repository,base,source,output):
 repository,base,source,output=[Path(x).resolve() for x in (repository,base,source,output)];output.mkdir(mode=0o700)
 lock=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text())
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 rows=[]
 for cosmic in (False,True):
  for network in ('offline','managed'):
   name=('cosmic' if cosmic else 'headless')+'-'+network
   params={'nixpkgsSource':str(source),'expectedSourceNarHash':lock['source_nar_hash'],'enableCosmic':cosmic,'networkPolicy':network}
   encoded=json.dumps(json.dumps(params));expr='let s=import (builtins.toPath '+json.dumps(str(repository/'distro/nix/live-image-eval.nix'))+') (builtins.fromJSON '+encoded+'); c=s.config; u=c.systemd.services.roko-startup-report; in { after=u.after; before=u.before; wantedBy=u.wantedBy; requires=u.requires; wants=u.wants; service=u.serviceConfig; failure=u.unitConfig.OnFailure; unit=c.systemd.units."roko-startup-report.service".text; failureUnit=c.systemd.units."roko-startup-report-failure.service".text; firstBoot=builtins.fromJSON c.environment.etc."roko/first-boot.json".text; networkManager=c.networking.networkmanager.enable; waitOnline=c.systemd.network.wait-online.enable; nmWait=c.systemd.services.NetworkManager-wait-online.enable or null; cosmic=c.services.desktopManager.cosmic.enable; }'
   expression=output/(name+'.nix');expression.write_text(expr)
   result=subprocess.run(prefix+['eval','--impure','--json','--file',str(expression)],env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')},capture_output=True,text=True,timeout=120)
   (output/(name+'.stderr')).write_text(result.stderr);(output/(name+'.stdout')).write_text(result.stdout)
   if result.returncode:rows.append({'case':name,'passed':False,'returncode':result.returncode});continue
   value=json.loads(result.stdout);service=value['service']
   passed=value['after']==['local-fs.target'] and set(value['before'])=={'multi-user.target','display-manager.service'} and value['wantedBy']==['multi-user.target'] and not value['requires'] and not value['wants'] and value['failure']==['roko-startup-report-failure.service']
   passed=passed and service['Type']=='oneshot' and service['DynamicUser'] and service['PrivateNetwork'] and service['ProtectSystem']=='strict' and service['NoNewPrivileges'] and service['TimeoutStartSec']=='15s' and service['RuntimeDirectoryPreserve']=='yes' and service['RuntimeDirectoryMode']=='0750'
   passed=passed and value['cosmic']==cosmic and value['networkManager']==(network=='managed') and value['firstBoot']['modelReady'] is False and value['firstBoot']['durableHistoryReady'] is False
   if network=='offline':passed=passed and not value['waitOnline'] and value['nmWait'] is False
   rows.append({'case':name,'passed':passed,'returncode':0,'evaluation':value})
 report={'passed':all(row['passed'] for row in rows),'cases':rows,'scope':'pinned Nix evaluation and generated unit text only','systemd_executed':False,'guest_booted':False,'build_completed':False,'host_activation':False,'sandbox_retried':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.output);print(json.dumps({'passed':r['passed'],'cases':[{k:v for k,v in row.items() if k!='evaluation'} for row in r['cases']]}));raise SystemExit(0 if r['passed'] else 1)
