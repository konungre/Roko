#!/usr/bin/env python3
"""Derive a separate avatar guest from the immutable, tested reduced session."""
import argparse,gzip,hashlib,importlib.util,json,os,stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
BASE=ROOT/'build/cosmic-session-guest-history/061e179a-passed'
OUT=ROOT/'build/basilisk-avatar-guest'
def sha(data):return hashlib.sha256(data).hexdigest()

def record(name,data,mode,ino,major=0,minor=0):
 fields=[ino,mode,0,0,1,0,len(data),0,0,major,minor,len(name.encode())+1,0]
 head=b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)
 head+=name.encode()+b'\0';head+=b'\0'*(-len(head)%4)
 return head+data+b'\0'*(-len(data)%4)
def read_archive(path):
 with gzip.open(path,'rb') as f:
  while True:
   h=f.read(110)
   if len(h)!=110 or h[:6]!=b'070701':raise ValueError('Invalid base newc header')
   v=[int(h[6+i*8:14+i*8],16) for i in range(13)]
   raw=f.read(v[11]);name=raw[:-1].decode()
   if not raw.endswith(b'\0'):raise ValueError('Invalid base name')
   f.read(-(110+v[11])%4);data=f.read(v[6]);f.read(-v[6]%4)
   if name=='TRAILER!!!':break
   if len(data)!=v[6] or name.startswith('/') or '..' in Path(name).parts:raise ValueError('Unsafe base entry')
   yield name,data,v[1],v[9],v[10]
def overlay(root,lock):
 raw=lock.read_bytes();j=json.loads(raw);out={}
 records=j['files'] if 'files' in j else [{'path':p,'sha256':h,'mode':stat.S_IMODE((root/p).stat().st_mode)} for p,h in j.items()]
 for r in records:
  p=Path(r['path'])
  if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe overlay path')
  path=root/p
  if path.is_symlink() or not path.is_file():raise ValueError('Only locked regular overlay files supported')
  data=path.read_bytes();mode=stat.S_IFREG|r['mode']
  if sha(data)!=r['sha256'] or stat.S_IMODE(path.stat().st_mode)!=r['mode']:raise ValueError('Overlay changed '+str(path))
  out[str(p)]=(data,mode,0,0)
 return out,{'root':str(root.relative_to(ROOT.parent)),'lock':str(lock.relative_to(ROOT.parent)),'lock_sha256':sha(raw),'files':len(out)}
def derive_init(data):
 old=b'( $BB sleep 300; echo ROKO_SESSION_FAILED guest-watchdog; finish ) &'
 new=b'(\n    $BB sleep 390\n    echo ROKO_AVATAR_WATCHDOG_SESSION_EXIT_REQUEST\n    $BB timeout 5 /usr/bin/dbus-send --session --type=method_call --print-reply --dest=com.system76.CosmicSession /com/system76/CosmicSession com.system76.CosmicSession.Exit\n    echo "ROKO_AVATAR_WATCHDOG_DBUS_RESULT $?"\n    $BB sleep 20\n    echo ROKO_SESSION_FAILED guest-watchdog\n    finish\n) &'
 if data.count(old)!=1:raise ValueError('Expected immutable base watchdog exactly once')
 data=data.replace(b'session_pid=$!\n', b'session_pid=$!\n'+(HERE/'direct-start.sh').read_bytes())
 return data.replace(old,new).replace(b'$BB chmod 700 /run/user/0', b'$BB mkdir -p /run/user/0/roko\n$BB chmod 700 /run/user/0/roko\n$BB chmod 700 /run/user/0')

def build():
 manifest=json.loads((BASE/'manifest.json').read_text()); archive=BASE/'session.cpio.gz'
 if manifest['build_id']!='061e179ae4a4473baa0b8f1669df10ade7ef6c85a99a93835752cb43c476f099' or sha(archive.read_bytes())!=manifest['initramfs_sha256']:raise ValueError('Tested session changed')
 files={};receipts=[];replacements={}
 specs=[(ROOT/'build-src/basilisk-stage/overlay-v2',ROOT/'build-src/basilisk-stage/overlay-v2.lock.json'),(ROOT/'build-src/basilisk-layer-stage/overlay-v1',ROOT/'build-src/basilisk-layer-stage/overlay-v1.lock.json'),(ROOT.parent/'roko-basilisk-stage-v2',ROOT.parent/'roko-basilisk-stage-v2.lock.json'),(ROOT/'build-src/omega-avatar-controller-stage/overlay-v1',ROOT/'build-src/omega-avatar-controller-stage/overlay-v1.lock.json'),(ROOT/'build-src/basilisk-stage/mime-overlay-v1',ROOT/'build-src/basilisk-stage/mime-overlay-v1.lock.json'),(ROOT/'build-src/basilisk-stage/gio-overlay-v1',ROOT/'build-src/basilisk-stage/gio-overlay-v1.lock.json'),(ROOT/'build-src/cosmic-dock-stage/avatar-v1',ROOT/'build-src/cosmic-dock-stage/avatar-v1.lock.json')]
 for root,lock in specs:
  layer,receipt=overlay(root,lock);receipts.append(receipt)
  for name,value in layer.items():
   if name in files and files[name]!=value:
    if root!=ROOT.parent/'roko-basilisk-stage-v2' or not (name.startswith('usr/share/roko/basilisk/') or name in ['usr/bin/roko-basilisk','usr/share/applications/roko-basilisk.desktop']):raise ValueError('Unequal overlay collision '+name)
    replacements[name]={'prior_sha256':sha(files[name][0]),'avatar_v2_sha256':sha(value[0])}
   files[name]=value
 # Explicit test wrapper preserves actual terminal/CLI argv; only test flag enables Exit.
 key='usr/share/applications/roko.desktop';old_entry=files[key];old_data=old_entry[0]
 lines=old_data.decode().splitlines();new_data=('\n'.join('Exec=/usr/bin/roko-console-fixture' if line.startswith('Exec=') else line for line in lines)+'\n').encode()
 replacements[key]={'prior_sha256':sha(old_data),'fixture_sha256':sha(new_data),'scope':'Kernel-flag-only exit after genuine console process returns'}
 files[key]=(new_data,*old_entry[1:])
 scripts={'direct-start.sh':sha((HERE/'direct-start.sh').read_bytes())}
 for local,dest,mode in [('observe-v4.py','usr/libexec/roko-avatar-observe.py',0o755),('launch.sh','usr/bin/roko-avatar-test',0o755),('console-fixture.sh','usr/bin/roko-console-fixture',0o755),('finish.sh','usr/bin/roko-avatar-finish',0o755),('com.roko.AvatarFinish.desktop','usr/share/applications/com.roko.AvatarFinish.desktop',0o444),('com.roko.AvatarTest.desktop','usr/share/applications/com.roko.AvatarTest.desktop',0o444)]:
  data=(HERE/local).read_bytes();scripts[local]=sha(data);files[dest]=(data,stat.S_IFREG|mode,0,0)
 # The original app, sprite and released session remain untouched.
 override_init=None
 entries={};seen=set();OUT.mkdir(parents=True,exist_ok=True)
 output_path=OUT/'avatar.cpio.gz';total=0;ino=0
 with output_path.open('wb') as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0,compresslevel=1) as output:
   def emit(name,data,mode,major=0,minor=0):
    nonlocal ino,total
    if name in entries:raise ValueError('Duplicate output '+name)
    ino+=1;chunk=record(name,data,mode,ino,major,minor);output.write(chunk);total+=len(chunk)
    entries[name]={'mode':mode,'bytes':len(data),'sha256':sha(data),'uid':0,'gid':0,'mtime':0,'rdevmajor':major,'rdevminor':minor}
   for name,data,mode,major,minor in read_archive(archive):
    expect=manifest['entries'].get(name)
    if not expect or expect['sha256']!=sha(data) or expect['mode']!=mode:raise ValueError('Base entry mismatch '+name)
    seen.add(name)
    if name in files:
     if files.pop(name)!=(data,mode,major,minor):raise ValueError('Unequal base collision '+name)
    if name=='init':
     original=sha(data);data=derive_init(data);override_init={'base_sha256':original,'derived_sha256':sha(data),'change':'Guest watchdog requests genuine sessionExit at390s, bounded5s call plus20s fallback; private root0700 cosmetic-event directory'}
    emit(name,data,mode,major,minor)
   if seen!=set(manifest['entries']):raise ValueError('Base entry set changed')
   for name in list(files):
    for parent in Path(name).parents:
     p=str(parent)
     if p!='.' and p not in entries:files.setdefault(p,(b'',stat.S_IFDIR|0o755,0,0))
   for name,value in sorted(files.items()):emit(name,*value)
   trailer=record('TRAILER!!!',b'',0,ino+1);output.write(trailer);output.write(b'\0'*(-(total+len(trailer))%512))
 identity={'base_build_id':manifest['build_id'],'base_initramfs_sha256':manifest['initramfs_sha256'],'overlays':receipts,'explicit_app_replacements':replacements,'scripts':scripts,'derived_init':override_init}
 result=dict(identity,build_id=sha(json.dumps(identity,sort_keys=True).encode()),entries=entries,initramfs_sha256=sha(output_path.read_bytes()),initramfs_bytes=output_path.stat().st_size,uncompressed_file_bytes=sum(e['bytes'] for e in entries.values()),boot_tested=False,scope='Separate disposable root COSMIC avatar test; no host access/network/autonomous actions')
 (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['build_id','initramfs_sha256','initramfs_bytes','uncompressed_file_bytes','boot_tested']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args()
 if a.build:build()
 else:print('Explicit --build required; separate output only')
