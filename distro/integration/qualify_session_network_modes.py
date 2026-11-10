"""Small real Nix module-merger fixture, not full NixOS/image evaluation."""
import argparse,hashlib,json,os,resource,subprocess
from pathlib import Path
from memory_budget import observe

def limits():
 resource.setrlimit(resource.RLIMIT_AS,(96*1024**2,96*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(3,3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def qualify(repository,base,source,output):
 repository,base,source,output=[Path(p).resolve() for p in (repository,base,source,output)];output.mkdir(mode=0o700)
 budget=observe();full_required=320*1024**2
 preflight={'memory':budget,'full_evaluation_required_headroom_bytes':full_required,'full_evaluation_attempted':False,'full_evaluation_admitted':budget['observed_headroom_bytes']>=full_required,'fixture_required_headroom_bytes':160*1024**2,'guest_started':False}
 (output/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 template='''let lib=import SOURCE/lib; b=lib.mkOption {type=lib.types.bool;default=true;};
 r=lib.evalModules {modules=[({lib,...}:{options={services.avahi.enable=b;services.geoclue2.enable=b;services.accounts-daemon.enable=b;services.dbus.enable=b;services.pipewire.enable=b;security.polkit.enable=b;nix.channel.enable=b;
 nix.nixPath=lib.mkOption {type=lib.types.listOf lib.types.str;default=["fixture"];};nix.registry=lib.mkOption {type=lib.types.attrs;default.fixture={};};nix.settings.substituters=lib.mkOption {type=lib.types.listOf lib.types.str;default=["normal-trusted-cache-fixture"];};nix.settings.flake-registry=lib.mkOption {type=lib.types.str;default="fixture";};systemd.network.wait-online.enable=b;systemd.services.NetworkManager-wait-online.enable=b;};config.services.avahi.enable=lib.mkDefault true;config.services.geoclue2.enable=lib.mkDefault true;})
 (import POLICY {inherit lib;offline=OFFLINE;}) USER];};in r.config'''.replace('SOURCE',str(source)).replace('POLICY',str(repository/'distro/nix/session-network-policy.nix'))
 cases=[('offline',True,'',False),('managed',False,'',False),('managed-user-disables-discovery',False,'{services.avahi.enable=false;services.geoclue2.enable=false;}',False),('offline-conflicting-force',True,'({lib,...}:{services.avahi.enable=lib.mkForce true;})',True)];rows=[]
 for name,offline,user,reject in cases:
  memory=observe()
  if memory['observed_headroom_bytes']<160*1024**2:raise ValueError('insufficient headroom for bounded module fixture')
  expr=template.replace('OFFLINE','true' if offline else 'false').replace('USER',user);path=output/(name+'.nix');path.write_text(expr)
  result=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')},capture_output=True,text=True,timeout=5,preexec_fn=limits)
  (output/(name+'.stdout')).write_text(result.stdout);(output/(name+'.stderr')).write_text(result.stderr)
  value=json.loads(result.stdout) if result.returncode==0 else None
  if reject:passed=result.returncode!=0 and 'conflicting definition' in result.stderr.lower()
  else:
   disabled=offline or bool(user)
   passed=result.returncode==0 and value['services']['avahi']['enable']==(not disabled) and value['services']['geoclue2']['enable']==(not disabled) and all(value['services'][n]['enable'] for n in ('accounts-daemon','dbus','pipewire')) and value['security']['polkit']['enable'] and value['nix']['channel']['enable']==(not offline) and bool(value['nix']['settings']['substituters'])==(not offline) and bool(value['nix']['nixPath'])==(not offline) and bool(value['nix']['registry'])==(not offline) and bool(value['nix']['settings']['flake-registry'])==(not offline) and value['systemd']['network']['wait-online']['enable']==(not offline) and value['systemd']['services']['NetworkManager-wait-online']['enable']==(not offline)
  rows.append({'case':name,'returncode':result.returncode,'passed':passed,'evaluation':value})
 report={'passed':all(row['passed'] for row in rows),'cases':rows,'preflight':preflight,'nixpkgs_pin':json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text()),'pin_reverified_this_run':False,'selected_library_hashes':{name:hashlib.sha256((source/'lib'/name).read_bytes()).hexdigest() for name in ('default.nix','modules.nix')},'source_hashes':{name:hashlib.sha256((repository/'distro/nix'/name).read_bytes()).hexdigest() for name in ('session-network-policy.nix','offline-startup.nix')},'limits':{'address_space_mib':96,'cpu_seconds':3,'wall_seconds':5},'full_nixos_evaluated':False,'image_built':False,'guest_started':False,'host_activation':False,'scope':'small actual Nix module merger with synthetic option defaults; not complete connected/offline runtime behavior'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.output);print(json.dumps({'passed':r['passed'],'cases':[{k:row[k] for k in ('case','returncode','passed')} for row in r['cases']]}));raise SystemExit(0 if r['passed'] else 1)
