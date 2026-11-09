#!/usr/bin/env python3
"""Small separately versioned Files diagnostics bootstrap; accepted root disk untouched."""
import argparse,gzip,hashlib,importlib.util,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];BASE=R/'build/disk-root-guest';OUT=R/'build/files-delta-guest'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
archive=module('corner_newc',R/'boot/basilisk-avatar-guest/build.py');delta=module('corner_delta',R/'boot/test-delta-root/prepare.py')
def sha(data):return hashlib.sha256(data).hexdigest()
def build():
 base=json.loads((BASE/'bootstrap.json').read_text());blob=(BASE/'bootstrap.cpio.gz').read_bytes()
 if sha(blob)!=base['initramfs_sha256'] or base['build_id']!=delta.ROOT_ID:raise ValueError('Accepted bootstrap changed')
 additions,receipt=delta.prepare('files');entries={};chunks=[];seen=set();ino=0
 def add(name,data,mode,major=0,minor=0):
  nonlocal ino
  if name in entries:raise ValueError('Duplicate bootstrap entry')
  ino+=1;chunks.append(archive.record(name,data,mode,ino,major,minor));entries[name]={'mode':mode,'bytes':len(data),'sha256':sha(data),'uid':0,'gid':0,'mtime':0,'rdevmajor':major,'rdevminor':minor}
 for name,data,mode,major,minor in archive.read_archive(BASE/'bootstrap.cpio.gz'):
  e=base['entries'].get(name,{})
  if e.get('sha256')!=sha(data) or e.get('mode')!=mode:raise ValueError('Base bootstrap entry changed')
  seen.add(name)
  if name in additions:raise ValueError('Unexpected delta collision')
  if name=='init':data=delta.derive_init(data)
  add(name,data,mode,major,minor)
 if seen!=set(base['entries']):raise ValueError('Base entry set differs')
 for name,value in sorted(additions.items()):add(name,*value)
 chunks.append(archive.record('TRAILER!!!',b'',0,ino+1));raw=b''.join(chunks);raw+=b'\0'*(-len(raw)%512)
 OUT.mkdir(mode=0o700,exist_ok=True);path=OUT/'bootstrap.cpio.gz'
 with path.open('xb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0,compresslevel=1) as g:g.write(raw)
 result={'build_id':base['build_id'],'delta_id':receipt['delta_id'],'root_sha256':delta.ROOT_SHA,'base_bootstrap_sha256':base['initramfs_sha256'],'initramfs_sha256':sha(path.read_bytes()),'initramfs_bytes':path.stat().st_size,'entries':entries,'delta':receipt,'builder_sha256':sha(Path(__file__).read_bytes()),'boot_tested':False,'scope':'Files/portal test files copied into guest tmpfs only; no root-disk mutation or GUI success claim'}
 with (OUT/'bootstrap.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({k:result[k] for k in ['build_id','delta_id','initramfs_sha256','initramfs_bytes','boot_tested']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args()
 if a.build:build()
 else:print('Explicit --build required; no root disk writes or VM.')
