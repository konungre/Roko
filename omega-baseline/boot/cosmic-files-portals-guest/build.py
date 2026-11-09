#!/usr/bin/env python3
"""Separate immutable Files/portal derivative; no disk mutation, service or VM."""
import argparse,gzip,hashlib,importlib.util,json,stat
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
BASE=ROOT/'build/cosmic-persistent-guest';OUT=ROOT/'build/cosmic-files-portals-guest'
LAYER=ROOT/'build-src/cosmic-files-portals-stage/overlay-v1';LOCK=LAYER.with_name('overlay-v1.lock.json')
BASE_ID='392024cd75b8a2565bf75e223a3fa0b807c8af1f26a797d5f7dbbba973415229'
RETAIN_MODE='usr/share/icons/hicolor/index.theme'
CACHE='usr/share/glib-2.0/schemas/gschemas.compiled'
s=importlib.util.spec_from_file_location('files_archive',ROOT/'boot/basilisk-avatar-guest/build.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def derive_init(data):
 old=b'session_pid=$!\n'
 if data.count(old)!=1:raise ValueError('Unknown session PID hook')
 return data.replace(old,old+b'/usr/libexec/roko-portal-session-env >/dev/console 2>&1 &\n')
def build():
 raw=(BASE/'manifest.json').read_bytes();base=json.loads(raw);archive=BASE/'persistent.cpio.gz'
 if base['build_id']!=BASE_ID or file_sha(archive)!=base['initramfs_sha256']:raise ValueError('Stable persistent image changed')
 locked=LOCK.read_bytes();layer=json.loads(locked);files={}
 for e in layer['files']:
  path=e['path'];p=LAYER/path
  if Path(path).is_absolute() or '..' in Path(path).parts or p.is_symlink() or not p.is_file():raise ValueError('Unsafe regular overlay')
  if file_sha(p)!=e['sha256'] or stat.S_IMODE(p.stat().st_mode)!=e['mode']:raise ValueError('Overlay changed '+path)
  files[path]=(p,stat.S_IFREG|e['mode'])
 for local,dest,mode in [('session-env.sh','usr/libexec/roko-portal-session-env',0o755),('probe.py','usr/libexec/roko-files-portals-probe.py',0o755)]:
  if dest in files:raise ValueError('Unexpected helper collision')
  files[dest]=(HERE/local,stat.S_IFREG|mode)
 OUT.mkdir(mode=0o700,exist_ok=True);output=OUT/'files-portals.cpio.gz';entries={};seen=set();replaced={};ino=0;total=0
 with output.open('xb') as rawout:
  with gzip.GzipFile(fileobj=rawout,mode='wb',filename='',mtime=0,compresslevel=1) as out:
   def emit(name,data,mode,major=0,minor=0):
    nonlocal ino,total
    if name in entries:raise ValueError('Duplicate output')
    ino+=1;blob=a.record(name,data,mode,ino,major,minor);out.write(blob);total+=len(blob)
    entries[name]={'mode':mode,'bytes':len(data),'sha256':sha(data),'uid':0,'gid':0,'mtime':0,'rdevmajor':major,'rdevminor':minor}
   for name,data,mode,major,minor in a.read_archive(archive):
    e=base['entries'].get(name,{})
    if e.get('sha256')!=sha(data) or e.get('mode')!=mode or e.get('rdevmajor',0)!=major or e.get('rdevminor',0)!=minor:raise ValueError('Base entry changed '+name)
    seen.add(name)
    if name in files:
     p,newmode=files.pop(name);new=p.read_bytes()
     if name==RETAIN_MODE and data==new and stat.S_IMODE(mode)==0o444 and stat.S_IMODE(newmode)==0o644:
      replaced[name]={'before_sha256':sha(data),'after_sha256':sha(data),'retained_mode':'0444','overlay_mode_not_applied':'0644','reason':'Identical authentic data retains existing stricter mode'}
      newmode=mode
     if (data,mode)!=(new,newmode):
      if name!=CACHE:raise ValueError('Unapproved overlay collision '+name)
      replaced[name]={'before_sha256':sha(data),'after_sha256':sha(new),'reason':'Authentic expanded GSettings schema compilation'}
      data,mode=new,newmode
    if name=='init':
     old=sha(data);data=derive_init(data);replaced[name]={'before_sha256':old,'after_sha256':sha(data),'reason':'Actual guest D-Bus activation environment only'}
    emit(name,data,mode,major,minor)
   if seen!=set(base['entries']):raise ValueError('Base set changed')
   dirs=set()
   for name in files:
    for parent in Path(name).parents:
     p=str(parent)
     if p!='.' and p not in entries:dirs.add(p)
   for name in sorted(dirs):emit(name,b'',stat.S_IFDIR|0o755)
   for name,(p,mode) in sorted(files.items()):emit(name,p.read_bytes(),mode)
   trailer=a.record('TRAILER!!!',b'',0,ino+1);out.write(trailer);out.write(b'\0'*(-(total+len(trailer))%512))
 identity={'base_build_id':BASE_ID,'base_initramfs_sha256':base['initramfs_sha256'],'base_manifest_sha256':sha(raw),'overlay_lock_sha256':sha(locked),'explicit_replacements':replaced,'source_sha256':{n:file_sha(HERE/n) for n in ['build.py','session-env.sh','probe.py']}}
 result=dict(identity,build_id=sha(json.dumps(identity,sort_keys=True).encode()),entries=entries,initramfs_sha256=file_sha(output),initramfs_bytes=output.stat().st_size,uncompressed_file_bytes=sum(e['bytes'] for e in entries.values()),boot_tested=False,scope='Separate genuine Files/applet/portal runtime; no GUI, portal permission or persistence proof yet')
 with (OUT/'manifest.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({k:result[k] for k in ['build_id','initramfs_sha256','initramfs_bytes','uncompressed_file_bytes','boot_tested']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');args=p.parse_args()
 if args.build:build()
 else:print('Preparation only; explicit --build required. No VM or disk changes.')
