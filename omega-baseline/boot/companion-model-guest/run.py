#!/usr/bin/env python3
"""Bounded combined COSMIC UI and real guest model, QMP inherited pipes only."""
import argparse,fcntl,json,os,re,signal,subprocess,threading,time
from pathlib import Path
import prepare
R=prepare.R;H=prepare.H;four=prepare.guest;base=four.base
session=prepare.load('combined_session',R/'boot/cosmic-session-guest/run.py')
old_ui=prepare.load('combined_gui_helpers',R/'boot/companion-controls-guest/run.py')
RESULT_PARENT=R/'results/companion-model-guest';BUILD_PARENT=R/'build/companion-model-guest'

def command(assets,bootstrap,root_fd,model_fd,model,result):
 args=base.command(assets,bootstrap,root_fd,model_fd,model)
 args[args.index('-serial')+1]='file:'+str(result/'serial.txt')
 args[args.index('-append')+1]+=' roko.files_fixture=1'
 args+=['-qmp','stdio','-device','virtio-gpu-pci','-device','virtio-keyboard-pci','-device','virtio-tablet-pci']
 return args

def run():
 RESULT_PARENT.mkdir(mode=0o700,exist_ok=True);BUILD_PARENT.mkdir(mode=0o700,exist_ok=True)
 lane=os.open(R/'results/granite-model-guest/recovery-lane.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(lane,fcntl.LOCK_EX|fcntl.LOCK_NB)
 attempt=1
 while (RESULT_PARENT/f'attempt-{attempt}').exists() or (BUILD_PARENT/f'attempt-{attempt}').exists():attempt+=1
 result=RESULT_PARENT/f'attempt-{attempt}';out=BUILD_PARENT/f'attempt-{attempt}';result.mkdir(mode=0o700);inbox=result/'commands';inbox.mkdir(mode=0o700)
 report={'passed':False,'status':'preflight','result_path':str(result.relative_to(R)),'boot_tested':False,'errors':[], 'actions':[],'captures':{},'memory_mib':6144,'tcg_cpus':4,'native_threads':4,'vm_wall_seconds':1500,'guest_watchdog_seconds':1410,'bridge_seconds':1080,'provider_seconds':930,'native_seconds':900,'host_rss_cap_bytes':7*1024**3,'host_available_floor_bytes':2*1024**3,'disk_floor_bytes':4*1024**3,'network_enabled':False,'model_copy_created':False,'host_directory_shared':False,'child_parent_death_signal':'SIGKILL','runner':four.process_identity(os.getpid()),'peak_qemu_rss_kib':0,'minimum_host_available_bytes':base.available()}
 root_fd=model_fd=proc=q=None;start=None;guard_errors=[];guard_stop=threading.Event();thread=None
 prior={sig:signal.signal(sig,four.cancelled) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
 termination_lock=threading.Lock()
 def terminate():
  with termination_lock:
   if proc is None:return
   for sig,seconds in ((signal.SIGTERM,3),(signal.SIGKILL,3)):
    if proc.poll() is not None:return
    try:os.killpg(proc.pid,sig)
    except ProcessLookupError:pass
    try:proc.wait(timeout=seconds);return
    except subprocess.TimeoutExpired:pass
   raise TimeoutError('QEMU remained after bounded termination')
 def serial():return (result/'serial.txt').read_text(errors='replace') if (result/'serial.txt').exists() else ''
 def persist(phase):
  report['status']=phase;report['heartbeat_unix_seconds']=time.time()
  if start is not None:report['elapsed_seconds']=round(time.monotonic()-start,3)
  summary={k:v for k,v in report.items() if k not in ('actions','captures','assembly','tooling_integrity')}
  summary['actions_count']=len(report['actions']);summary['captures_count']=len(report['captures'])
  four.atomic_json(result/'progress.json',summary)
 def guard():
  last=time.monotonic()
  while not guard_stop.wait(.1) and proc.poll() is None:
   try:
    rss=0
    for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines():
     if line.startswith(('VmHWM:','VmRSS:')):rss=max(rss,int(line.split()[1]))
    report['peak_qemu_rss_kib']=max(report['peak_qemu_rss_kib'],rss)
    available=base.available();report['minimum_host_available_bytes']=min(report['minimum_host_available_bytes'],available)
    report['host_available_bytes']=available;report['free_disk_bytes']=base.disk_free()
    logs=sum(p.stat().st_size for p in (result/'serial.txt',result/'qemu-stderr.txt') if p.exists())
    if rss*1024>report['host_rss_cap_bytes']:raise MemoryError('Host QEMU RSS cap crossed')
    if available<report['host_available_floor_bytes']:raise MemoryError('Host MemAvailable floor crossed')
    if report['free_disk_bytes']<base.RESERVE:raise ValueError('Host disk floor crossed')
    if logs>8*1024**2:raise ValueError('Serial/stderr8MiB cap crossed')
    if time.monotonic()-start>1500:raise TimeoutError('Host VM1500s deadline crossed')
    if time.monotonic()-last>=5:persist('running');last=time.monotonic()
   except FileNotFoundError:
    if proc.poll() is not None:return
   except BaseException as exc:
    guard_errors.append(type(exc).__name__+': '+str(exc))
    try:terminate()
    except BaseException as failure:guard_errors.append('Guard termination: '+str(failure))
    return
 def capture(name):
  if not re.fullmatch('[A-Za-z0-9_-]{1,70}',name) or len(report['captures'])>=40:raise ValueError('Invalid or excessive capture')
  path=result/(name+'.ppm')
  if path.exists():raise ValueError('Never overwrite raw capture')
  q.call('screendump',{'filename':str(path)});data=path.read_bytes()
  if len(data)>4*1024**2:raise ValueError('Capture exceeds4MiB')
  report['captures'][name]={'path':str(path.relative_to(R)),'sha256':prepare.sha(data),'elapsed_seconds':round(time.monotonic()-start,3)}
 def action(a):
  kind=a['action']
  if kind=='capture':capture(a['name'])
  elif kind=='text':old_ui.typed_text(q,a['text'])
  elif kind=='key':q.key(a['key'])
  elif kind=='chord':q.chord(a['modifier'],a['key'])
  elif kind in ('click','move'):
   x,y=a['x'],a['y']
   if not(0<=x<1280 and 0<=y<800):raise ValueError('Pointer outside display')
   q.call('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(x*32767/1279)}},{'type':'abs','data':{'axis':'y','value':round(y*32767/799)}}]})
   if kind=='click':
    time.sleep(.2)
    for down in (True,False):q.call('input-send-event',{'events':[{'type':'btn','data':{'down':down,'button':'left'}}]});time.sleep(.1)
  elif kind=='modified-drag':
   points=a['points'];button=a.get('button','left')
   if button not in ('left','right') or not 2<=len(points)<=12:raise ValueError('Invalid drag')
   action({'action':'move','x':points[0][0],'y':points[0][1]})
   def key(down):q.call('input-send-event',{'events':[{'type':'key','data':{'down':down,'key':{'type':'qcode','data':'meta_l'}}}]})
   def btn(down):q.call('input-send-event',{'events':[{'type':'btn','data':{'down':down,'button':button}}]})
   key(True);btn(True)
   try:
    for x,y in points[1:]:action({'action':'move','x':x,'y':y});time.sleep(1)
   finally:btn(False);key(False)
  elif kind=='stop':raise InterruptedError('Explicit bounded abort: '+str(a.get('reason','unspecified')))
  else:raise ValueError('Unsupported action')
 try:
  if base.disk_free()<base.RESERVE+160*1024**2 or base.available()<8*1024**3:raise ValueError('Admission requires8GiB available and4GiB+160MiB disk')
  integrity=base.load('combined_tooling_integrity',R/'boot/verify-tooling.py').verify()
  if not integrity['success']:raise ValueError('Tooling integrity failed')
  report['tooling_integrity']=integrity
  assets=json.loads((R/'boot/boot-assets.lock.json').read_text())
  for name in ('qemu','kernel'):
   if prepare.sha(Path(assets[name]['path']).read_bytes())!=assets[name]['sha256']:raise ValueError('Asset pin changed')
  # Validate preserved native four-core closure before new combined assembly.
  prepare.guest.prepare_fourcore.validate()
  root_fd=base.root_image.open_image(R);report['root_before']=base.host_model.metadata(os.fstat(root_fd));report['root_sha256_before']=base.fd_hash(root_fd)
  if report['root_sha256_before']!=prepare.corner.ROOT_SHA:raise ValueError('Root changed')
  model_fd,report['model_before']=base.host_model.open_model();fcntl.flock(model_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  bootstrap,report['assembly']=prepare.assemble(out)
  args=command(assets,bootstrap,root_fd,model_fd,report['model_before'],result);report['command']=args
  report['source_sha256']={str(p.relative_to(R)):prepare.sha(p.read_bytes()) for p in H.glob('*.py')}
  if base.disk_free()<base.RESERVE+160*1024**2 or base.available()<8*1024**3:raise ValueError('Reserve changed before launch')
  persist('admitted')
  with (result/'qemu-stderr.txt').open('xb') as err:
   parent=os.getpid();start=time.monotonic()
   proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,pass_fds=(root_fd,model_fd),start_new_session=True,preexec_fn=lambda:four.child_guard(parent),env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
   report.update(boot_tested=True,qemu=four.process_identity(proc.pid));q=session.Controls(proc)
   thread=threading.Thread(target=guard,name='resource-guard',daemon=True);thread.start();persist('running')
   print(json.dumps({'started':True,'result_path':report['result_path'],'qemu':report['qemu']}),flush=True)
   deadline=time.monotonic()+10
   while not q.greeting and time.monotonic()<deadline:q.poll(.1)
   if not q.greeting:raise TimeoutError('QMP greeting deadline')
   q.call('qmp_capabilities');handled=set();ready=False
   while proc.poll() is None:
    q.poll(.1)
    if guard_errors:raise RuntimeError('; '.join(guard_errors))
    if not ready and 'ROKO_TERMINAL_SHELL_READY ' in serial():
     ready=True;four.atomic_json(result/'ready.json',{'ready':True,'elapsed_seconds':time.monotonic()-start});capture('terminal-ready')
    for path in sorted(inbox.glob('*.json')):
     if path.name in handled:continue
     handled.add(path.name);a=json.loads(path.read_text());entry={'file':path.name,'action':a,'elapsed_seconds':round(time.monotonic()-start,3)}
     try:action(a);entry['accepted']=True
     except (ValueError,OSError,TimeoutError) as error:entry.update(accepted=False,error=str(error))
     report['actions'].append(entry);four.atomic_json(result/'actions.json',report['actions'])
    if not ready and time.monotonic()-start>240:raise TimeoutError('Graphical terminal readiness240s deadline')
   report['qemu_returncode']=proc.returncode
  log=serial();report['session_exit_verified']='ROKO_SESSION_EXIT 0' in log.splitlines();report['guest_watchdog_fired']=any(x in log for x in ('ROKO_AVATAR_WATCHDOG_SESSION_EXIT_REQUEST','ROKO_SESSION_FAILED guest-watchdog'))
  report['normal_exit']=report['qemu_returncode']==0 and report['session_exit_verified'] and 'ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST' in log and not report['guest_watchdog_fired']
  if not report['normal_exit']:raise ValueError('Normal guest session exit not proven')
  report['lifecycle_passed']=True
 except BaseException as error:report['errors'].append(type(error).__name__+': '+str(error))
 finally:
  guard_stop.set()
  if thread:thread.join(timeout=7)
  report['errors'].extend(x for x in guard_errors if x not in report['errors'])
  try:persist('cleanup')
  except BaseException as error:report['errors'].append('Cleanup heartbeat: '+str(error))
  finally:
   try:terminate()
   except BaseException as error:report['errors'].append('QEMU termination: '+str(error))
  report['qemu_running_after_cleanup']=proc is not None and proc.poll() is None
  if proc is not None:report['qemu_returncode']=proc.returncode
  if model_fd is not None:
   try:report['model_after']=base.host_model.verify(model_fd,report.get('model_before'));report['model_unchanged']=report['model_before']==report['model_after']
   except BaseException as error:report['errors'].append('Model postcheck: '+str(error))
   os.close(model_fd)
  if root_fd is not None:
   try:
    report['root_after']=base.host_model.metadata(os.fstat(root_fd));report['root_sha256_after']=base.fd_hash(root_fd)
    report['root_unchanged']=report['root_before']==report['root_after'] and report['root_sha256_before']==report['root_sha256_after']==prepare.corner.ROOT_SHA
   except BaseException as error:report['errors'].append('Root postcheck: '+str(error))
   os.close(root_fd)
  if q is not None:
   try:four.atomic_json(result/'qmp.json',q.responses)
   except BaseException as error:report['errors'].append('QMP receipt: '+str(error))
  report['passed']=not report['errors'] and report.get('lifecycle_passed',False) and report.get('model_unchanged',False) and report.get('root_unchanged',False)
  report['pass_scope']='Lifecycle and immutable inputs only; separate human/raw UI and CLI evaluation required'
  for p in result.iterdir():
   if p.suffix in ('.ppm','.txt'):
    report[p.name+'_sha256']=prepare.sha(p.read_bytes());p.chmod(0o444)
  try:
   persist('completed');four.atomic_json(result/'validation.json',report);(result/'validation.json').chmod(0o444)
  finally:
   os.close(lane)
   for sig,handler in prior.items():signal.signal(sig,handler)
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args()
 if a.run:
  r=run();print(json.dumps({k:r.get(k) for k in ('passed','result_path','errors','qemu_returncode')}),flush=True);raise SystemExit(0 if r['passed'] else 1)
 print('Explicit --run required; no VM launched.')
