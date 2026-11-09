#!/usr/bin/env python3
"""Two real desktop boots, one admitted private disk; actual GUI keyboard input only."""
import argparse,hashlib,importlib.util,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'build/cosmic-persistent-guest';RESULT=ROOT/'results/cosmic-persistent-guest'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
session=load('persistent_session_controls',ROOT/'boot/cosmic-session-guest/run.py')
storage=load('persistent_disk_admission',ROOT/'boot/desktop-filesystem-guest/storage.py')
COMMANDS=[
 'create desktop-persist --goal "Desktop recovery"',
 'evidence desktop-persist source --source fixture:desktop --text "Arithmetic: 7 * 8."',
 'propose desktop-persist --tool record_answer --arguments \'{"text":"56"}\' --evidence source',
 'check desktop-persist --checker arithmetic',
 'close desktop-persist',
 'show desktop-persist']
def type_text(q,text):
 if len(text)>512:raise ValueError('Bounded fixture text only')
 plain={' ':'spc','-':'minus','/':'slash','.':'dot',"'":'apostrophe',':':None,'[':'bracket_left',']':'bracket_right',';':'semicolon',',':'comma','=':'equal'}
 shifted={'"':'apostrophe',':':'semicolon','{':'bracket_left','}':'bracket_right','*':'8','_':'minus'}
 for char in text:
  if char in shifted:q.chord('shift',shifted[char])
  elif 'A'<=char<='Z':q.chord('shift',char.lower())
  elif char.isascii() and (char.islower() or char.isdigit()):q.key(char)
  elif char in plain and plain[char]:q.key(plain[char])
  else:raise ValueError('Unsupported fixture character '+repr(char))
  time.sleep(.045)
def result_text_count(data):
 w,h,pixels=session.verifier.read_ppm(data)
 if w!=1280 or h!=800:return 0
 return sum(min(c)>=100 and max(c)-min(c)<8 for y in range(350,600) for x in range(25,830) if (c:=pixels[(y*w+x)*3:(y*w+x)*3+3]))

def preflight():
 m=json.loads((OUT/'manifest.json').read_text());archive=OUT/'persistent.cpio.gz'
 with archive.open('rb') as stream:
  if hashlib.file_digest(stream,'sha256').hexdigest()!=m['initramfs_sha256']:raise ValueError('Persistent archive hash changed')
 reader=load('persistent_archive_reader',ROOT/'boot/basilisk-avatar-guest/build.py');seen=set()
 for name,data,mode,major,minor in reader.read_archive(archive):
  e=m['entries'].get(name,{})
  if name in seen or e.get('sha256')!=hashlib.sha256(data).hexdigest() or e.get('mode')!=mode or e.get('rdevmajor',0)!=major or e.get('rdevminor',0)!=minor:raise ValueError('Persistent archive entry changed: '+name)
  seen.add(name)
 if seen!=set(m['entries']):raise ValueError('Persistent archive entry set differs')
 g=session.build.base.graphics();assets,_,_,_,_,_=g.inputs()
 if not g.load_module('persistent_tooling_integrity','verify-tooling.py').verify()['success']:raise ValueError('Tooling changed')
 c=g.v.command(assets['qemu']['path'],assets['kernel']['path'],OUT/'persistent.cpio.gz');c[c.index('-m')+1]='4096';c[c.index('-append')+1]+=' roko.avatar_fixture=1'
 c+=['-qmp','stdio','-device','virtio-gpu-pci','-device','virtio-keyboard-pci','-device','virtio-tablet-pci']
 return m,c
def boot(m,base,fd,phase):
 result=RESULT/phase;result.mkdir();session.RESULT=result
 command=storage.attach_command(base,fd,phase);command[command.index('-serial')+1]='file:'+str(result/'serial.txt')
 report={'phase':phase,'build_id':m['build_id'],'initramfs_sha256':m['initramfs_sha256'],'command':command,'host_deadline_seconds':450,'captures':{},'typed_commands':[],'errors':[],'automated_passed':False,'ui_review_required':True,'root_disposable_prototype':True,'host_disks_attached':False,'network_enabled':False}
 with (result/'qemu-stderr.txt').open('wb') as err:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,pass_fds=(fd,));q=session.Controls(p);start=time.monotonic();deadline=start+450
  def log():return session.read_serial()
  def wait(test,seconds,reason):
   end=min(deadline,time.monotonic()+seconds)
   while time.monotonic()<end:
    q.poll(.1)
    if test():return
    if p.poll() is not None:raise ValueError('Guest exited before '+reason)
   raise TimeoutError(reason)
  def capture(name):
   dest=result/(name+'.ppm')
   if dest.exists():raise ValueError('Capture overwrite refused')
   q.call('screendump',{'filename':str(dest)});data=dest.read_bytes();report['captures'][name]={'sha256':session.old.digest(data),'elapsed_ms':round((time.monotonic()-start)*1000)};return data
  def move(x,y):q.call('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(x*32767/1279)}},{'type':'abs','data':{'axis':'y','value':round(y*32767/799)}}]})
  def click(x,y):
   move(x,y)
   for down in (True,False):q.call('input-send-event',{'events':[{'type':'btn','data':{'down':down,'button':'left'}}]});time.sleep(.2)
  def typed(text):
   type_text(q,text);q.key('ret');report['typed_commands'].append({'text':text,'elapsed_ms':round((time.monotonic()-start)*1000)})
  try:
   wait(lambda:q.greeting,10,'QMP greeting');q.call('qmp_capabilities')
   wait(lambda:'ROKO_DESKTOP_STORAGE_MOUNTED '+phase in log().splitlines(),90,'actual ext4 mount')
   wait(lambda:'ROKO_AVATAR_OBSERVE_V3 ' in log(),130,'actual avatar start')
   end=min(deadline,time.monotonic()+60);i=0
   while time.monotonic()<end:
    data=capture('controls-ready-'+str(i));w,h,pixels=session.verifier.read_ppm(data)
    sample=[pixels[(y*w+x)*3:(y*w+x)*3+3] for y in range(165,350,8) for x in range(480,800,8)]
    if sum(min(c)>180 for c in sample)>len(sample)*3//5:break
    time.sleep(2);i+=1
   else:raise TimeoutError('Actual controls pixels')
   click(640,135);time.sleep(3);click(640,291)
   wait(lambda:'"kind": "desktop_launch_return", "result": true' in log(),25,'actual Console button/Gio launch')
   end=min(deadline,time.monotonic()+90);i=0
   while time.monotonic()<end:
    data=capture('console-ready-'+str(i))
    if session.terminal_pixels_ready(data) and session.terminal_text_ready(data):break
    time.sleep(2);i+=1
   else:raise TimeoutError('Actual console visible text')
   click(450,350);time.sleep(4);click(450,350);time.sleep(4)
   for text in COMMANDS if phase=='write' else ['show desktop-persist']:
    typed(text);time.sleep(3)
   expected='ROKO_DESKTOP_STORAGE_'+phase.upper()+'_PASSED'
   wait(lambda:expected in log().splitlines(),max(1,deadline-time.monotonic()-45),'actual stored snapshot '+phase)
   if phase=='write':
    rows=[json.loads(x.split(' ',1)[1]) for x in log().splitlines() if x.startswith('ROKO_DESKTOP_STORAGE_CONSOLES ')]
    if not rows or not rows[-1]:raise ValueError('No real persistent console process record')
   move(1100,600);end=min(deadline-25,time.monotonic()+75);i=0
   while time.monotonic()<end:
    data=capture('result-content-'+str(i))
    if result_text_count(data)>1000:break
    time.sleep(3);i+=1
   else:raise TimeoutError('Actual result text not yet rendered')
   time.sleep(5);capture('task-result');time.sleep(5);capture('task-result-settled')
   typed('quit')
   wait(lambda:'ROKO_SESSION_EXIT 0' in log().splitlines(),max(1,deadline-time.monotonic()),'genuine session Exit')
   p.wait(timeout=10)
  except (ValueError,OSError,TimeoutError,subprocess.TimeoutExpired) as e:report['errors'].append(str(e))
  finally:
   if p.poll() is None:
    try:capture('last-before-stop')
    except Exception:pass
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
   (result/'qmp.json').write_text(json.dumps(q.responses,indent=2)+'\n')
 lines=log().splitlines();report['qemu_returncode']=p.returncode
 report['normal_console_completion']=all(x in lines for x in ['ROKO_AVATAR_CONSOLE_EXIT 0','ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST','ROKO_SESSION_EXIT 0','ROKO_DESKTOP_STORAGE_UNMOUNTED']) and not any('WATCHDOG' in x or 'guest-watchdog' in x for x in lines)
 report['automated_passed']=not report['errors'] and p.returncode==0 and report['normal_console_completion'] and ('ROKO_DESKTOP_STORAGE_'+phase.upper()+'_PASSED') in lines
 (result/'validation.json').write_text(json.dumps(report,indent=2)+'\n');return report
def run_pair():
 m,c=preflight();archived=session.old.preserve_previous(RESULT,ROOT/'results/cosmic-persistent-guest-attempts');report={'passed':False,'previous_attempt_archive':str(archived),'build_id':m['build_id'],'boots':{},'ui_review_required':True}
 try:
  with storage.admitted() as fd:
   for phase in ('write','read'):
    value=boot(m,c,fd,phase);report['boots'][phase]=value
    report['fsck_after_'+phase]=storage.fsck(fd)
    if not value['automated_passed']:break
   if all(report['boots'].get(p,{}).get('automated_passed') for p in ('write','read')):
    report['storage']=storage.validate_pair((RESULT/'write/serial.txt').read_text(),(RESULT/'read/serial.txt').read_text());report['automated_passed']=True
 except (ValueError,OSError,subprocess.SubprocessError) as exc:
  report['error']=str(exc);report['automated_passed']=False
 (RESULT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');return report
def run_read_check():
 global RESULT
 RESULT=ROOT/'results/cosmic-persistent-read-check'
 m,c=preflight();archived=session.old.preserve_previous(RESULT,ROOT/'results/cosmic-persistent-read-check-attempts')
 report={'passed':False,'scope':'Additional read-only GUI recovery confirmation; original two-boot evidence unchanged','previous_attempt_archive':str(archived),'build_id':m['build_id'],'ui_review_required':True}
 try:
  with storage.admitted() as fd:
   report['boot']=boot(m,c,fd,'read');report['fsck']=storage.fsck(fd)
   if report['boot']['automated_passed']:
    report['storage']=storage.validate_pair((ROOT/'results/cosmic-persistent-guest/write/serial.txt').read_text(),(RESULT/'read/serial.txt').read_text());report['automated_passed']=True
 except (ValueError,OSError,subprocess.SubprocessError) as exc:report['error']=str(exc)
 (RESULT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);choice=ap.add_mutually_exclusive_group();choice.add_argument('--run-pair',action='store_true');choice.add_argument('--run-read-check',action='store_true');a=ap.parse_args()
 if a.run_pair:print(json.dumps(run_pair(),indent=2))
 elif a.run_read_check:print(json.dumps(run_read_check(),indent=2))
 else:m,c=preflight();print(json.dumps({'boot_tested':False,'build_id':m['build_id'],'command_without_storage':c},indent=2))
