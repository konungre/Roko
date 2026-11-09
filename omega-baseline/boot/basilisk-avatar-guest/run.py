#!/usr/bin/env python3
"""Bounded QMP-pipe avatar test with local file-queued diagnostic controls."""
import argparse,gzip,importlib.util,json,re,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'build/basilisk-avatar-guest';RESULT=ROOT/'results/basilisk-avatar-guest'
s=importlib.util.spec_from_file_location('tested_session_runner',ROOT/'boot/cosmic-session-guest/run.py');session=importlib.util.module_from_spec(s);s.loader.exec_module(session)
def preflight():
 m=json.loads((OUT/'manifest.json').read_text());data=(OUT/'avatar.cpio.gz').read_bytes();g=session.build.base.graphics();assets,kernel,_,_,_,sources=g.inputs()
 if session.old.digest(data)!=m['initramfs_sha256'] or g.b.inspect(gzip.decompress(data))!=m['entries']:raise ValueError('Avatar archive changed')
 for n,h in m['scripts'].items():
  if session.old.digest((HERE/n).read_bytes())!=h:raise ValueError('Avatar script changed '+n)
 c=g.v.command(assets['qemu']['path'],assets['kernel']['path'],OUT/'avatar.cpio.gz');c[c.index('-m')+1]='4096';c[c.index('-serial')+1]='file:'+str(RESULT/'serial.txt')
 c[c.index('-append')+1]+=' roko.avatar_fixture=1'
 c+=['-qmp','stdio','-device','virtio-gpu-pci','-device','virtio-keyboard-pci','-device','virtio-tablet-pci'];return g,m,c

def run(g,m,command):
 if not g.load_module('avatar_tooling_integrity','verify-tooling.py').verify()['success']:raise ValueError('Tooling integrity failed')
 archived=session.old.preserve_previous(RESULT,ROOT/'results/basilisk-avatar-guest-attempts');inbox=RESULT/'commands';inbox.mkdir()
 report={'passed':False,'boot_tested':True,'build_id':m['build_id'],'initramfs_sha256':m['initramfs_sha256'],'previous_attempt_archive':str(archived),'command':command,'timeout_seconds':450,'actions':[],'captures':{},'errors':[],'scope':'Actual avatar GUI/input test; no host disks/network/GPU/autonomous dispatch'}
 session.RESULT=RESULT
 with (RESULT/'qemu-stderr.txt').open('wb') as err:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err);q=session.Controls(p);deadline=time.monotonic()+450;start=time.monotonic()
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
   elif kind=='text':q.text(action['text'])
   elif kind=='chord':q.chord(action['modifier'],action['key'])
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
   # Direct fixture launch is explicit; earlier actual launcher/button proof stays separate.
   wait(lambda:'ROKO_AVATAR_OBSERVE_V3 ' in session.read_serial(),90)
   capture('avatar-start')
   time.sleep(8)
   controls_end=min(deadline,time.monotonic()+45);i=0
   while time.monotonic()<controls_end:
    time.sleep(2);data=capture('controls-ready-'+str(i));w,h,pixels=session.verifier.read_ppm(data)
    sample=[pixels[(y*w+x)*3:(y*w+x)*3+3] for y in range(165,350,8) for x in range(480,800,8)]
    if sum(min(c)>180 for c in sample)>len(sample)*3//5:break
    i+=1
   else:raise TimeoutError('Actual avatar controls not visibly ready')
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
 report['exit_origin']='fixture' if 'ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST' in session.read_serial().splitlines() else ('watchdog' if 'ROKO_AVATAR_WATCHDOG_SESSION_EXIT_REQUEST' in session.read_serial().splitlines() else 'unverified');report['qemu_returncode']=p.returncode;report['session_exit_verified']='ROKO_SESSION_EXIT 0' in session.read_serial().splitlines();report['guest_watchdog_fired']='ROKO_SESSION_FAILED guest-watchdog' in session.read_serial().splitlines();report['lifecycle_passed']=report['session_exit_verified'] and p.returncode==0 and not report['guest_watchdog_fired'];report['normal_fixture_completion']=report['lifecycle_passed'] and report['exit_origin']=='fixture' and not report['errors'] and ('ROKO_AVATAR_CONSOLE_EXIT 0' in session.read_serial().splitlines() or any(a['action'].get('action')=='finish' and a.get('accepted') for a in report['actions']));(RESULT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true');a=ap.parse_args();g,m,c=preflight();print(json.dumps(run(g,m,c) if a.run else {'boot_tested':False,'build_id':m['build_id'],'command':c},indent=2))
