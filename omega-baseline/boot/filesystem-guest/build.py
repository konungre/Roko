#!/usr/bin/env python3
"""Separate minimal ext4 guest builder; no image format or VM launch."""
import gzip
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re
import stat
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'build/filesystem-guest'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
archive=module('files_archive',ROOT/'boot/build.py')
vm=module('files_vm',ROOT/'boot/test_vm.py')
def sha(data): return hashlib.sha256(data).hexdigest()

def inputs():
    base=ROOT/'boot/tooling/root'
    lock=json.loads((ROOT/'boot/tooling-files.lock.json').read_text())['files']
    assets=json.loads((ROOT/'boot/boot-assets.lock.json').read_text())
    sources={}
    def read(path):
        rel=str(path.relative_to(base)); record=lock[rel]; data=path.read_bytes()
        if path.is_symlink() or record['kind']!='file' or sha(data)!=record['sha256'] or stat.S_IMODE(path.stat().st_mode)!=record['mode']:
            raise ValueError('Unpinned tooling file: '+rel)
        sources[rel]=sha(data); return data
    kernel=Path(assets['kernel']['path']).name.removeprefix('vmlinuz-')
    config=read(base/'boot'/('config-'+kernel)).decode()
    for name in ['CONFIG_VIRTIO','CONFIG_VIRTIO_PCI','CONFIG_DEVTMPFS','CONFIG_PROC_FS','CONFIG_SYSFS']:
        if name+'=y\n' not in config: raise ValueError('Required built-in unavailable: '+name)
    modules={}; order=[]
    def add(name):
        if name in modules: return
        paths=list((base/'usr/lib/modules'/kernel/'kernel').rglob(name+'.ko.xz'))
        if len(paths)!=1: raise ValueError('Ambiguous/missing module: '+name)
        data=lzma.decompress(read(paths[0]))
        deps=re.search(rb'\x00depends=([^\x00]*)',data)
        magic=re.search(rb'\x00vermagic=([^\x00]*)',data)
        if not deps or not magic or magic[1].split()[0].decode()!=kernel: raise ValueError('Module metadata mismatch')
        modules[name]={'path':str(paths[0].relative_to(ROOT)), 'sha256':sha(paths[0].read_bytes()),'decompressed_sha256':sha(data),'depends':deps[1].decode().split(',') if deps[1] else []}
        for dep in modules[name]['depends']: add(dep)
        order.append(name)
    add('virtio_blk'); add('crc32c_generic'); add('ext4')  # ext4 requests crc32c through crypto API, outside depends.
    for key in ['kernel','qemu']: vm.verified_asset(assets[key])
    busybox=read(Path(assets['busybox']['path'])); archive.check_elf(busybox)
    return assets,kernel,busybox,modules,order,sources

def build():
    assets,kernel,busybox,modules,order,sources=inputs()
    OUT.mkdir(mode=0o700,exist_ok=True)
    if OUT.is_symlink() or stat.S_IMODE(OUT.stat().st_mode)!=0o700: raise ValueError('Output directory must be private')
    binary=OUT/'files-probe'
    if binary.is_symlink(): raise ValueError('Probe output symlink')
    subprocess.run(['gcc','-static','-O2','-Wall','-Wextra','-Werror','-Wl,--build-id=none',str(HERE/'probe.c'),'-o',str(binary)],check=True,timeout=60)
    helper=binary.read_bytes(); archive.check_elf(helper)
    scripts={name:sha((HERE/name).read_bytes()) for name in ['probe.c','init.sh','build.py']}
    identity={'sources':sources,'modules':modules,'scripts':scripts,'probe_sha256':sha(helper)}
    build_id=sha(json.dumps(identity,sort_keys=True).encode()); files={}
    def put(name,data,mode,major=0,minor=0): files[name]=(data,mode,major,minor)
    for name in ['bin','etc','dev','proc','sys','modules','data']: put(name,b'',stat.S_IFDIR|0o755)
    put('dev/console',b'',stat.S_IFCHR|0o600,5,1)
    for name,data,mode in [('bin/busybox',busybox,0o755),('bin/files-probe',helper,0o755),('init',(HERE/'init.sh').read_bytes(),0o755),('etc/probe-id',(build_id+'\n').encode(),0o444),('etc/kernel-release',(kernel+'\n').encode(),0o444),('etc/module-order',('\n'.join(order)+'\n').encode(),0o444)]: put(name,data,stat.S_IFREG|mode)
    put('bin/sh',b'busybox',stat.S_IFLNK|0o777)
    for name,record in modules.items(): put('modules/'+name+'.ko',lzma.decompress((ROOT/record['path']).read_bytes()),stat.S_IFREG|0o444)
    raw=b''.join(archive.entry(name,data,mode,i+1,major,minor) for i,(name,(data,mode,major,minor)) in enumerate(sorted(files.items())))
    raw+=archive.entry('TRAILER!!!',b'',0,len(files)+1); raw+=b'\0'*(-len(raw)%512)
    data=gzip.compress(raw,compresslevel=1,mtime=0)
    manifest=dict(identity,build_id=build_id,kernel_release=kernel,module_order=order,entries=archive.inspect(raw),initramfs_sha256=sha(data),boot_tested=False)
    (OUT/'files.cpio.gz').write_bytes(data); (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__': print(json.dumps(build(),indent=2))
