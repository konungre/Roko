#!/usr/bin/env python3
"""Build deterministic boot-probe initramfs without mounting or installing."""
import gzip,hashlib,io,json,stat,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BOOT=ROOT/'boot';OUT=ROOT/'build/boot'
def sha(data):return hashlib.sha256(data).hexdigest()
def entry(name,data,mode,ino,major=0,minor=0):
 if name.startswith('/') or '..' in name.split('/'):raise ValueError('Unsafe archive path')
 name=name.encode()+b'\0'
 fields=[ino,mode,0,0,2 if stat.S_ISDIR(mode) else 1,0,len(data),0,0,major,minor,len(name),0]
 header=b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)+name
 return header+b'\0'*((-len(header))%4)+data+b'\0'*((-len(data))%4)
def inspect(raw):
 offset=0;found={}
 while True:
  if raw[offset:offset+6]!=b'070701':raise ValueError('Invalid newc header')
  if len(raw)-offset<110:raise ValueError('Truncated header')
  fields=[int(raw[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
  mode=fields[1];size=fields[6];length=fields[11]
  if length<1 or length>4096 or offset+110+length>len(raw):raise ValueError('Invalid name length')
  offset+=110;name=raw[offset:offset+length-1].decode()
  if raw[offset+length-1]!=0:raise ValueError('Unterminated name')
  offset+=length;offset+=(-offset)%4
  data=raw[offset:offset+size]
  if len(data)!=size:raise ValueError('Truncated archive')
  offset+=size;offset+=(-offset)%4
  if name=='TRAILER!!!':break
  if name in found:raise ValueError('Duplicate path')
  found[name]={'mode':mode,'bytes':size,'sha256':sha(data),'uid':fields[2],'gid':fields[3],'mtime':fields[5],'rdevmajor':fields[9],'rdevminor':fields[10]}
 return found
def check_elf(data):
 if data[:4]!=b'\x7fELF' or data[4]!=2 or data[5]!=1 or struct.unpack_from('<H',data,18)[0]!=62:raise ValueError('Expected x86_64 ELF')
 phoff=struct.unpack_from('<Q',data,32)[0];phsize,phnum=struct.unpack_from('<HH',data,54)
 if any(struct.unpack_from('<I',data,phoff+i*phsize)[0]==3 for i in range(phnum)):raise ValueError('Dynamic interpreter dependency')
def main(profile_bytes=None):
 OUT.mkdir(parents=True,exist_ok=True)
 profile=(BOOT/'profile.json').read_bytes() if profile_bytes is None else profile_bytes
 busybox=None
 asset=json.loads((BOOT/'boot-assets.lock.json').read_text())['busybox']
 if asset is not None:
  if type(asset) is not dict or set(asset)!={'path','sha256'}:raise ValueError('Invalid BusyBox asset')
  busybox=Path(asset['path']).read_bytes()
  if sha(busybox)!=asset['sha256']:raise ValueError('BusyBox digest mismatch')
  check_elf(busybox)
 build_id=sha((BOOT/'init.c').read_bytes()+profile+(busybox or b''))
 flags=['-nostdlib','-static','-Os','-s','-fno-pie','-no-pie','-fno-stack-protector','-fno-builtin','-mno-sse','-mno-mmx','-fno-asynchronous-unwind-tables','-fno-ident','-Wl,--build-id=none',f'-DROKO_BUILD_ID="{build_id}"']
 subprocess.run(['gcc',*flags,str(BOOT/'init.c'),'-o',str(OUT/'init')],check=True,timeout=60)
 data=(OUT/'init').read_bytes()
 check_elf(data)
 files=[('dev',b'',stat.S_IFDIR|0o755,0,0),('dev/console',b'',stat.S_IFCHR|0o600,5,1),('etc',b'',stat.S_IFDIR|0o755,0,0),('etc/roko-profile.json',profile,stat.S_IFREG|0o444,0,0),('init',data,stat.S_IFREG|0o755,0,0),('proc',b'',stat.S_IFDIR|0o755,0,0),('sys',b'',stat.S_IFDIR|0o755,0,0)]
 if busybox is not None:
  files.extend([('tmp',b'',stat.S_IFDIR|0o1777,0,0),('bin',b'',stat.S_IFDIR|0o755,0,0),('bin/busybox',busybox,stat.S_IFREG|0o755,0,0),('bin/sh',b'busybox',stat.S_IFLNK|0o777,0,0)])
  files.append(('licenses',b'',stat.S_IFDIR|0o755,0,0))
  for license_file in sorted((BOOT/'licenses').iterdir()):
   if license_file.is_file():files.append(('licenses/'+license_file.name,license_file.read_bytes(),stat.S_IFREG|0o444,0,0))
  files.sort(key=lambda x:x[0])
 raw=b''.join(entry(name,contents,mode,i+1,major,minor) for i,(name,contents,mode,major,minor) in enumerate(files))
 raw+=entry('TRAILER!!!',b'',0,len(files)+1);raw+=b'\0'*((-len(raw))%512)
 records=inspect(raw);buffer=io.BytesIO()
 with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=0,compresslevel=9) as stream:stream.write(raw)
 compressed=buffer.getvalue();assert gzip.decompress(compressed)==raw
 (OUT/'roko-initramfs.cpio.gz').write_bytes(compressed)
 report={'build_id':build_id,'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],'flags':flags,'init_sha256':sha(data),'initramfs_sha256':sha(compressed),'initramfs_bytes':len(compressed),'entries':records,'boot_tested':False,'cosmic_included':False,'busybox_included':busybox is not None,'scope':'Own freestanding no-libc PID-1 probe and deterministic initramfs; no kernel or VM runtime included'}
 (OUT/'build-manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
