#!/usr/bin/env python3
"""Assemble existing CPython + real Roko controller atop approved BusyBox initramfs."""
import gzip,hashlib,importlib.util,io,json,lzma,os,re,stat,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BOOT=ROOT/'boot';OUT=ROOT/'build/boot'
spec=importlib.util.spec_from_file_location('roko_boot_builder',BOOT/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
CONTROLLER={'scripts/roko.py':'opt/roko/scripts/roko.py',
            'adapters/working_state.py':'opt/roko/adapters/working_state.py',
            'adapters/state_store.py':'opt/roko/adapters/state_store.py',
            'adapters/package_inventory.py':'opt/roko/adapters/package_inventory.py',
            'adapters/avatar_events.py':'opt/roko/adapters/avatar_events.py'}
def main():
 profile_data=json.loads((BOOT/'profile.json').read_text())
 profile_data['kind']='busybox-roko-controller-userland'
 profile_data['vm']['memory_mib']=512
 profile_bytes=(json.dumps(profile_data,sort_keys=True,indent=2)+'\n').encode()
 b.main(profile_bytes)
 manifest=json.loads((OUT/'build-manifest.json').read_text())
 assets=json.loads((BOOT/'boot-assets.lock.json').read_text())
 if assets['busybox'] is None:raise SystemExit('Approved BusyBox required')
 files={};sources={}
 def put(name,data,mode,source=None):
  if name.startswith('/') or '..' in name.split('/'):raise ValueError('Unsafe guest path')
  if name in files:raise ValueError('Duplicate guest path '+name)
  files[name]=(data,mode,0,0)
  parent=Path(name).parent
  while str(parent)!='.':
   files.setdefault(str(parent),(b'',stat.S_IFDIR|0o755,0,0));parent=parent.parent
  if source:sources[name]={'source':str(source),'sha256':b.sha(data)}
 def copy(source,name,mode=0o644):put(name,Path(source).read_bytes(),stat.S_IFREG|mode,source)
 # Reconstruct known base entries, keeping the original approved BusyBox.
 profile=(BOOT/'profile.json').read_bytes()
 put('dev',b'',stat.S_IFDIR|0o755);files['dev/console']=(b'',stat.S_IFCHR|0o600,5,1)
 for name in ['proc','sys','tmp','var','var/lib','var/lib/roko']:put(name,b'',stat.S_IFDIR|(0o1777 if name=='tmp' else 0o755))
 copy(OUT/'init','init',0o755);put('etc/roko-profile.json',profile_bytes,stat.S_IFREG|0o444)
 copy(assets['busybox']['path'],'bin/busybox',0o755);put('bin/sh',b'busybox',stat.S_IFLNK|0o777)
 for license_file in sorted((BOOT/'licenses').iterdir()):
  if license_file.is_file():copy(license_file,'licenses/'+license_file.name,0o444)
 base=Path(sys.base_prefix)
 python=base/'bin/python3.12';copy(python,'opt/roko/python/bin/python3.12',0o755)
 stdlib=base/'lib/python3.12'
 excluded={'site-packages','__pycache__','ensurepip','idlelib','lib-dynload','test','tkinter','turtledemo','venv'}
 for source in sorted(stdlib.rglob('*.py')):
  rel=source.relative_to(stdlib)
  if any(part in excluded for part in rel.parts):continue
  copy(source,'opt/roko/python/lib/python3.12/'+str(rel))
 # Existing approved Debian runtime libraries satisfy the interpreter's ELF needs.
 needed=subprocess.check_output(['ldd',str(python)],text=True)
 for source in re.findall(r'=> (/[^ ]+)',needed):
  name=Path(source).name
  local=BOOT/'tooling/root/usr/lib/x86_64-linux-gnu'/name
  if not local.is_file():raise SystemExit('Missing approved runtime library: '+name)
  copy(local,'lib/x86_64-linux-gnu/'+name,0o755)
 copy(BOOT/'tooling/root/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2','lib64/ld-linux-x86-64.so.2',0o755)
 for source,name in CONTROLLER.items():
  copy(ROOT/source,name)
 copy(ROOT/'granite-model.lock.json','opt/roko/granite-model.lock.json')
 copy(BOOT/'tooling-packages.lock.json','opt/roko/boot/tooling-packages.lock.json')
 copy(BOOT/'userland/guest-smoke.py','opt/roko/guest-smoke.py')
 for name in ['persistence.py','persistence-check.py']:
  copy(BOOT/'userland'/name,'opt/roko/'+name)
 modules=list((BOOT/'tooling/root/usr/lib/modules').glob('*/kernel/drivers/block/virtio_blk.ko.xz'))
 if len(modules)!=1:raise SystemExit('Expected exactly one approved virtio block module')
 put('opt/roko/virtio_blk.ko',lzma.decompress(modules[0].read_bytes()),stat.S_IFREG|0o644,modules[0])
 petta_spec=importlib.util.spec_from_file_location('roko_guest_petta_files',BOOT/'userland/petta_files.py')
 petta=importlib.util.module_from_spec(petta_spec);petta_spec.loader.exec_module(petta)
 for source,name,mode in petta.file_mappings(ROOT,base):
  if name not in files:copy(source,name,mode)
 wrapper=b'#!/bin/sh\nexport PYTHONHOME=/opt/roko/python\nexport PATH=/bin\nexec /opt/roko/python/bin/python3.12 /opt/roko/scripts/roko.py --state-dir /var/lib/roko "$@"\n'
 put('bin/roko',wrapper,stat.S_IFREG|0o755)
 raw=b''.join(b.entry(name,data,mode,i+1,major,minor) for i,(name,(data,mode,major,minor)) in enumerate(sorted(files.items())))
 raw+=b.entry('TRAILER!!!',b'',0,len(files)+1);raw+=b'\0'*((-len(raw))%512)
 b.inspect(raw)
 buffer=io.BytesIO()
 with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=0,compresslevel=9) as stream:stream.write(raw)
 data=buffer.getvalue();(OUT/'roko-initramfs.cpio.gz').write_bytes(data)
 manifest.update({'initramfs_sha256':b.sha(data),'initramfs_bytes':len(data),'uncompressed_bytes':len(raw),'entries':b.inspect(raw),'guest_python':sys.version,'userland_included':True,'persistence_included':True,'model_included':False,'scope':'Approved BusyBox, existing CPython, Roko controller, PeTTa/Janus and Omega message-state subset; no COSMIC or model'})
 (OUT/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (BOOT/'guest-userland-files.lock.json').write_text(json.dumps({'scope':'Observed existing host CPython and approved Debian libraries; not a rebuilt/pinned-source Python toolchain','files':sources},indent=2)+'\n')
 print(json.dumps({k:manifest[k] for k in ['initramfs_sha256','initramfs_bytes','uncompressed_bytes','userland_included','model_included']},indent=2))
if __name__=='__main__':main()
