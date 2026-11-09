"""Read-only user-session input diagnostics. No IPC connects or readiness claim."""
import argparse,json,os,re,stat,time
from pathlib import Path
from startup_report import write_report,resource_status
from memory_budget import read_bound

def inspect_session(env,uid=None):
 uid=os.getuid() if uid is None else uid
 checks={'non_root':uid!=0,'desktop_env_cosmic':'COSMIC' in env.get('XDG_CURRENT_DESKTOP','').split(':'),'wayland_session':env.get('XDG_SESSION_TYPE')=='wayland','private_runtime':False,'owned_wayland_socket':False,'owned_session_bus_socket':False}
 runtime=Path(env.get('XDG_RUNTIME_DIR',''))
 try:
  before=runtime.lstat()
  checks['private_runtime']=runtime.is_absolute() and runtime.resolve()==runtime and stat.S_ISDIR(before.st_mode) and before.st_uid==uid and stat.S_IMODE(before.st_mode)==0o700
  if checks['private_runtime']:
   display=env.get('WAYLAND_DISPLAY','')
   if re.fullmatch('[A-Za-z0-9_.-]{1,128}',display) and display not in ('.','..'):
    try:
     socket=(runtime/display).lstat();checks['owned_wayland_socket']=stat.S_ISSOCK(socket.st_mode) and socket.st_uid==uid
    except OSError:pass
   address=env.get('DBUS_SESSION_BUS_ADDRESS','')
   if address.startswith('unix:path='):
    bus=Path(address[len('unix:path='):].split(',',1)[0])
    if bus==runtime/'bus':
     try:
      socket=bus.lstat();checks['owned_session_bus_socket']=stat.S_ISSOCK(socket.st_mode) and socket.st_uid==uid
     except OSError:pass
   after=runtime.lstat()
   if (before.st_dev,before.st_ino,before.st_uid,before.st_mode)!=(after.st_dev,after.st_ino,after.st_uid,after.st_mode):
    checks.update(private_runtime=False,owned_wayland_socket=False,owned_session_bus_socket=False)
 except (OSError,ValueError):pass
 return {'schema':'roko-cosmic-session-inputs-v1','status':'inputs-observed-unqualified' if all(checks.values()) else 'incomplete','sampled_monotonic_ns':time.monotonic_ns(),'checks':checks,'issues':[name+'-not-observed' for name,value in checks.items() if not value],'cosmic_session_qualified':False,'interactive_ready':False,'inference_qualified':False,'execution_authorized':False,'scope':'environment labels and local socket metadata only; no compositor, bus, portal, audio or model health proof'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();report=inspect_session(os.environ)
 try:
  boot_id=read_bound('/proc/sys/kernel/random/boot_id',64).strip()
  if not re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',boot_id):raise ValueError('invalid boot identity')
  report['boot_id']=boot_id
 except (OSError,ValueError):
  report['boot_id']=None;report['status']='incomplete';report['issues'].append('boot-identity-not-observed')
 invocation=os.environ.get('INVOCATION_ID','');report['invocation_id']=invocation if re.fullmatch('[0-9a-f]{32}',invocation) else None
 if report['invocation_id'] is None:report['status']='incomplete';report['issues'].append('invocation-identity-not-observed')
 report['resources']=resource_status(6144,'/proc/meminfo','/sys/fs/cgroup');write_report(a.output,report,mode=0o600);print(json.dumps({'status':report['status'],'issues':report['issues'],'interactive_ready':False},sort_keys=True))
