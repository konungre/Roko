#!/usr/bin/env python3
"""Bounded real Files/portal guest controls; fixed private disk read-only."""
import argparse,gzip,hashlib,importlib.util,json,os,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'build/portal-input-guest';RESULT=ROOT/'results/portal-input-guest'
s=importlib.util.spec_from_file_location('tested_session_runner',ROOT/'boot/cosmic-session-guest/run.py');session=importlib.util.module_from_spec(s);s.loader.exec_module(session)
p=importlib.util.spec_from_file_location('files_persistent_tools',ROOT/'boot/cosmic-persistent-guest/run.py');persistent=importlib.util.module_from_spec(p);p.loader.exec_module(persistent)
storage=persistent.storage
def typed_text(q,text):
 if len(text)>512:raise ValueError('Text length limit')
 for char in text:
  if char=='>':q.chord('shift','dot')
  elif char=='&':q.chord('shift','7')
  else:persistent.type_text(q,char)

sys.path.insert(0,str(ROOT/'boot/disk-root-guest'))
import image as root_image
import runner_support as root_support
def fd_hash(fd):
 with os.fdopen(os.dup(fd),'rb') as stream:
  stream.seek(0);value=hashlib.file_digest(stream,'sha256').hexdigest()
 os.lseek(fd,0,os.SEEK_SET);return value
def preflight(fd):
 m=json.loads((OUT/'bootstrap.json').read_text());v=json.loads((ROOT/'build/disk-root-guest/validation.json').read_text());data=(OUT/'bootstrap.cpio.gz').read_bytes();g=session.build.base.graphics();assets,_,_,_,_,_=g.inputs()
 if m['build_id']!='32e03cfba11b02412dddd0a0a14c56b03a1290dcb5fa0e6710524b9f3ef78c80' or not v['passed'] or fd_hash(fd)!=v['root_sha256']:raise ValueError('Readonly root identity changed')
 if session.old.digest(data)!=m['initramfs_sha256'] or g.b.inspect(gzip.decompress(data))!=m['entries']:raise ValueError('Tiny bootstrap changed')
 c=g.v.command(assets['qemu']['path'],assets['kernel']['path'],OUT/'bootstrap.cpio.gz');c[c.index('-m')+1]='4096';c[c.index('-serial')+1]='file:'+str(RESULT/'serial.txt');c[c.index('-append')+1]+=' roko.files_fixture=1'
 c+=['-qmp','stdio','-device','virtio-gpu-pci','-device','virtio-keyboard-pci','-device','virtio-tablet-pci']
 return g,m,root_support.attach(c,fd,phase='none'),v

def run(g,m,command,fd):
 if not g.load_module('avatar_tooling_integrity','verify-tooling.py').verify()['success']:raise ValueError('Tooling integrity failed')
 archived=session.old.preserve_previous(RESULT,ROOT/'results/portal-input-guest-attempts');inbox=RESULT/'commands';inbox.mkdir()
 report={'passed':False,'boot_tested':True,'build_id':m['build_id'],'delta_id':m.get('delta_id'),'initramfs_sha256':m['initramfs_sha256'],'previous_attempt_archive':str(archived),'command':command,'timeout_seconds':450,'actions':[],'captures':{},'errors':[],'scope':'Actual Files/portal diagnostics test on unchanged read-only root with tmpfs-only delta; no controller disk, host disks, network, GPU or autonomy'}
 session.RESULT=RESULT
 with (RESULT/'qemu-stderr.txt').open('wb') as err:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,pass_fds=(fd,));q=session.Controls(p);deadline=time.monotonic()+450;start=time.monotonic()
  def capture(name):
   if not re.fullmatch('[a-zA-Z0-9_-]+',name):raise ValueError('Invalid capture name')
   dest=RESULT/(name+'.ppm')
   if dest.exists():raise ValueError('Never overwrite capture')
   q.call('screendump',{'filename':str(dest)});data=dest.read_bytes();report['captures'][name]={'path':dest.name,'sha256':session.old.digest(data),'elapsed_ms':round((time.monotonic()-start)*1000)};return data
  def wait(predicate,seconds):
   end=min(deadline,time.monotonic()+seconds)
   while time.monotonic()<end:
    q.poll(.15)
    if predicate():return
    if p.poll() is not None:raise ValueError('Guest exited early')
   raise TimeoutError('Guest condition timeout')
  def wait_search_results(prefix):
   end=min(deadline,time.monotonic()+35);i=0
   while time.monotonic()<end:
    data=capture(prefix+'-'+str(i));w,h,pixels=session.verifier.read_ppm(data)
    row=[pixels[(y*w+x)*3:(y*w+x)*3+3] for y in range(130,170,5) for x in range(400,900,10)]
    if sum(max(c)-min(c)<5 and 25<=c[0]<=80 for c in row)>len(row)*.65:return
    time.sleep(2);i+=1
   raise TimeoutError('Launcher result row not rendered')
  def do(action):
   kind=action['action']
   if kind=='stop':
    report['errors'].append('Explicit bounded test abort: '+str(action.get('reason','unspecified')))
    q.call('quit')
   elif kind=='finish':
    # Genuine trusted desktop fixture calls the existing private session bus.
    q.chord('meta_l','slash');time.sleep(5);q.text('end session probe');time.sleep(8);wait_search_results('finish-search-ready');q.key('ret')
   elif kind=='capture':capture(action['name'])
   elif kind=='key':q.key(action['key'])
   elif kind=='text':typed_text(q,action['text'])
   elif kind=='chord':q.chord(action['modifier'],action['key'])
   elif kind=='shortcut':
    modifiers=action['modifiers'];key=action['key']
    if not isinstance(modifiers,list) or not 1<=len(modifiers)<=2 or len(set(modifiers))!=len(modifiers) or any(x not in ('ctrl','shift','alt','meta_l') for x in modifiers) or key not in ('n','c','v','a','l'):raise ValueError('Unsupported bounded shortcut')
    def event(code,down):return {'type':'key','data':{'down':down,'key':{'type':'qcode','data':code}}}
    q.call('input-send-event',{'events':[event(x,True) for x in modifiers]+[event(key,True),event(key,False)]+[event(x,False) for x in reversed(modifiers)]})
   elif kind=='modified-drag':
    # Pinned COSMIC input/mod.rs uses logo+left/right for genuine move/resize.
    button=action.get('button','left');points=action['points']
    if button not in ('left','right') or not 2<=len(points)<=12 or any(not isinstance(p,list) or len(p)!=2 or not(0<=p[0]<1280 and 0<=p[1]<800) for p in points):raise ValueError('Invalid bounded modified drag')
    def key(down):q.call('input-send-event',{'events':[{'type':'key','data':{'down':down,'key':{'type':'qcode','data':'meta_l'}}}]})
    def btn(down):q.call('input-send-event',{'events':[{'type':'btn','data':{'down':down,'button':button}}]})
    do({'action':'move','x':points[0][0],'y':points[0][1]});time.sleep(1)
    key(True);time.sleep(.5);btn(True)
    try:
     time.sleep(1)
     for x,y in points[1:]:
      do({'action':'move','x':x,'y':y});time.sleep(1)
    finally:btn(False);key(False)
   elif kind=='move':
    x,y=action['x'],action['y']
    if not(0<=x<1280 and 0<=y<800):raise ValueError('Pointer outside virtual display')
    q.call('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(x*32767/1279)}},{'type':'abs','data':{'axis':'y','value':round(y*32767/799)}}]})
   elif kind=='button':
    if action['button'] not in ('left','right','middle') or not isinstance(action['down'],bool):raise ValueError('Invalid pointer button')
    q.call('input-send-event',{'events':[{'type':'btn','data':{'down':action['down'],'button':action['button']}}]})
   else:raise ValueError('Unsupported bounded control '+kind)
  try:
   wait(lambda:q.greeting,10);q.call('qmp_capabilities')
   wait(lambda:'cosmic-panel' in session.process_snapshot(session.read_serial()),110)
   wait(lambda:'ROKO_TERMINAL_SHELL_READY ' in session.read_serial(),150)
   end=min(deadline,time.monotonic()+90);i=0
   while time.monotonic()<end:
    data=capture('terminal-ready-'+str(i))
    if session.terminal_pixels_ready(data) and session.terminal_text_ready(data):break
    time.sleep(2);i+=1
   else:raise TimeoutError('Actual terminal prompt not visible')
   (RESULT/'ready.json').write_text(json.dumps({'ready':True,'controls':str(inbox),'remaining_seconds':round(deadline-time.monotonic())})+'\n')
   handled=set()
   while p.poll() is None and time.monotonic()<deadline:
    q.poll(.1)
    for path in sorted(inbox.glob('*.json')):
     if path.name in handled:continue
     handled.add(path.name);a=json.loads(path.read_text());entry={'file':path.name,'action':a,'elapsed_ms':round((time.monotonic()-start)*1000)}
     try:do(a);entry['accepted']=True
     except (ValueError,OSError,TimeoutError) as exc:entry['accepted']=False;entry['error']=str(exc)
     report['actions'].append(entry);(RESULT/'actions.json').write_text(json.dumps(report['actions'],indent=2)+'\n')
    if 'ROKO_SESSION_EXIT 0' in session.read_serial().splitlines():p.wait(timeout=10);break
   if p.poll() is None:raise TimeoutError('Avatar host deadline')
  except (ValueError,OSError,TimeoutError,subprocess.TimeoutExpired) as exc:report['errors'].append(str(exc))
  finally:
   if p.poll() is None and q.greeting:
    try:capture('last-before-stop')
    except Exception:pass
   if p.poll() is None:p.terminate()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
   (RESULT/'qmp.json').write_text(json.dumps(q.responses,indent=2)+'\n')
 report['exit_origin']='fixture' if 'ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST' in session.read_serial().splitlines() else ('watchdog' if 'ROKO_AVATAR_WATCHDOG_SESSION_EXIT_REQUEST' in session.read_serial().splitlines() else 'unverified');report['qemu_returncode']=p.returncode;report['session_exit_verified']='ROKO_SESSION_EXIT 0' in session.read_serial().splitlines();report['guest_watchdog_fired']=any(x in session.read_serial().splitlines() for x in ['ROKO_SESSION_FAILED guest-watchdog','ROKO_AVATAR_WATCHDOG_SESSION_EXIT_REQUEST']);report['lifecycle_passed']=report['session_exit_verified'] and p.returncode==0 and not report['guest_watchdog_fired'];report['normal_fixture_completion']=report['lifecycle_passed'] and report['exit_origin']=='fixture' and not report['errors'] and ('ROKO_AVATAR_CONSOLE_EXIT 0' in session.read_serial().splitlines() or any(a['action'].get('action')=='finish' and a.get('accepted') for a in report['actions']));(RESULT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true');args=ap.parse_args()
 fd=root_image.open_image(ROOT)
 try:
  g,m,c,verified=preflight(fd)
  if args.run:
   result=run(g,m,c,fd);result['root_sha256_before']=verified['root_sha256'];result['root_sha256_after']=fd_hash(fd);result['root_unchanged']=result['root_sha256_before']==result['root_sha256_after'];result['controller_disk_attached']=False
   (RESULT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
  else:print(json.dumps({'boot_tested':False,'build_id':m['build_id'],'command':c},indent=2))
 finally:os.close(fd)
