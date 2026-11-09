"""Bounded Nix fragment/mini-schema evaluation and native static COSMIC graph checks."""
import argparse,hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path

def limits():
 resource.setrlimit(resource.RLIMIT_AS,(192*1024**2,192*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(5,5));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def qualify(repository,base,source,upstream_target,output):
 repository,base,source,upstream_target,output=[Path(x).resolve() for x in (repository,base,source,upstream_target,output)];output.mkdir(mode=0o700)
 prefix=[str(base/'root/usr/bin/nix'),'--extra-experimental-features','nix-command','--store','local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),'--offline','--option','allow-import-from-derivation','false']
 def evaluate(label,expression):
  path=output/(label+'.nix');path.write_text(expression)
  run=subprocess.run(prefix+['eval','--impure','--json','--file',str(path)],env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')},capture_output=True,text=True,timeout=10,preexec_fn=limits)
  (output/(label+'.stdout')).write_text(run.stdout);(output/(label+'.stderr')).write_text(run.stderr)
  if run.returncode:raise ValueError('bounded Nix '+label+' failed: '+run.stderr[-2048:])
  return json.loads(run.stdout)
 service=evaluate('session-fragment','import '+str(repository/'distro/nix/cosmic-session-ordering.nix')+' {pkgs.python3='+json.dumps(str(Path(sys.executable).parent.parent))+';program='+json.dumps(str(repository/'distro/nix'))+';}')
 # Mini schema is a fixture, not a full NixOS configuration. It evaluates the
 # actual override fragment against mkDefault true and retained local services.
 expression='''let lib=import SOURCE/lib; b=lib.mkOption {type=lib.types.bool;default=true;};
 result=lib.evalModules {modules=[({lib,...}:{options={
 services.avahi.enable=b;services.geoclue2.enable=b;services.accounts-daemon.enable=b;services.dbus.enable=b;services.pipewire.enable=b;security.polkit.enable=b;
 nix.channel.enable=b;nix.nixPath=lib.mkOption {type=lib.types.listOf lib.types.str;default=["fixture"];};nix.registry=lib.mkOption {type=lib.types.attrs;default.fixture={};};
 nix.settings.substituters=lib.mkOption {type=lib.types.listOf lib.types.str;default=["fixture"];};nix.settings.flake-registry=lib.mkOption {type=lib.types.str;default="fixture";};
 systemd.network.wait-online.enable=b;systemd.services.NetworkManager-wait-online.enable=b;};
 config.services.avahi.enable=lib.mkDefault true;config.services.geoclue2.enable=lib.mkDefault true;})
 (import POLICY {inherit lib;})];};in result.config'''.replace('SOURCE',str(source)).replace('POLICY',str(repository/'distro/nix/offline-startup.nix'))
 offline=evaluate('offline-mini-schema',expression)
 assert service['wantedBy']==['cosmic-session.target'] and service['after']==['cosmic-session.target'] and service['partOf']==['cosmic-session.target'] and service['unitConfig']['DefaultDependencies'] is False and service['serviceConfig']['Restart']=='no'
 assert not offline['services']['avahi']['enable'] and not offline['services']['geoclue2']['enable'] and all(offline['services'][name]['enable'] for name in ('accounts-daemon','dbus','pipewire')) and offline['security']['polkit']['enable'] and not offline['systemd']['network']['wait-online']['enable']
 units=output/'units';units.mkdir();(output/'run').mkdir(mode=0o700);(output/'home').mkdir(mode=0o700)
 shutil.copy2(upstream_target,units/'cosmic-session.target')
 for name in ('graphical-session.target','graphical-session-pre.target','xdg-desktop-autostart.target'):
  src=Path('/usr/lib/systemd/user')/name
  if not src.exists():raise ValueError('static graph prerequisite absent: '+name)
  shutil.copy2(src,units/name)
 for name in ('basic.target','shutdown.target'):(units/name).write_text('[Unit]\nDefaultDependencies=no\nDescription=Static graph boundary fixture\n')
 def value(v):return ('yes' if v else 'no') if type(v) is bool else ' '.join(v) if isinstance(v,list) else str(v)
 text='[Unit]\nDescription=Roko COSMIC diagnostic fixture\nAfter=cosmic-session.target\nPartOf=cosmic-session.target\nDefaultDependencies=no\n[Service]\n'+'\n'.join(k+'='+value(v) for k,v in service['serviceConfig'].items())+'\n'
 target=units/'roko-cosmic-session-report.service';target.write_text(text)
 wants=units/'cosmic-session.target.wants';wants.mkdir();(wants/target.name).symlink_to('../'+target.name)
 command=['/usr/bin/systemd-analyze','--user','--generators=no','--man=no','--recursive-errors=yes','verify',str(units/'cosmic-session.target'),str(target)]
 env={'PATH':'/usr/bin:/bin','HOME':str(output/'home'),'XDG_RUNTIME_DIR':str(output/'run'),'SYSTEMD_UNIT_PATH':str(units)}
 rows=[]
 for label,negative in [('valid-no-gating',False),('ordering-cycle',True)]:
  target.write_text(text.replace('DefaultDependencies=no','DefaultDependencies=no\nBefore=cosmic-session.target') if negative else text)
  run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=10,preexec_fn=limits)
  (output/(label+'.stdout')).write_text(run.stdout);(output/(label+'.stderr')).write_text(run.stderr)
  passed=run.returncode!=0 and 'cycle' in run.stderr.lower() if negative else run.returncode==0
  rows.append({'case':label,'returncode':run.returncode,'passed':passed})
 target.write_text(text)
 report={'passed':all(row['passed'] for row in rows),'static_graph_cases':rows,'session_fragment':service,'offline_mini_schema':offline,'upstream_target_sha256':hashlib.sha256(upstream_target.read_bytes()).hexdigest(),'source_hashes':{name:hashlib.sha256((repository/'distro/nix'/name).read_bytes()).hexdigest() for name in ('offline-startup.nix','cosmic-session-ordering.nix','cosmic_session_report.py')},'scope':'bounded real Nix fragments/mini schema and static graph; not full NixOS evaluation, instantiated image or user manager execution','host_activation':False,'guest_started':False}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('base');p.add_argument('source');p.add_argument('upstream_target');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.base,a.source,a.upstream_target,a.output);print(json.dumps({'passed':r['passed'],'static_graph_cases':r['static_graph_cases']}));raise SystemExit(0 if r['passed'] else 1)
