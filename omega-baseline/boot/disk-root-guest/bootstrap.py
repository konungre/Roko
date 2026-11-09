"""Prepare a tiny root-switch initramfs from existing approved kernel modules/BusyBox."""
import gzip
import importlib.util
import json
from pathlib import Path
import stat
import source

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'build/disk-root-guest'
s=importlib.util.spec_from_file_location('disk_root_module_builder',ROOT/'boot/filesystem-guest/build.py')
fs=importlib.util.module_from_spec(s);s.loader.exec_module(fs)

def prepare_files(build_id):
    _,kernel,busybox,modules,order,sources=fs.inputs()
    import lzma
    files={}
    def put(name,data,mode,major=0,minor=0):files[name]=(data,mode,major,minor)
    for name in ['bin','dev','proc','sys','newroot','etc','modules']:put(name,b'',stat.S_IFDIR|0o755)
    put('dev/console',b'',stat.S_IFCHR|0o600,5,1)
    put('bin/busybox',busybox,stat.S_IFREG|0o755)
    put('bin/sh',b'busybox',stat.S_IFLNK|0o777)
    put('init',(HERE/'init.sh').read_bytes(),stat.S_IFREG|0o755)
    put('etc/root-build-id',(build_id+'\n').encode(),stat.S_IFREG|0o444)
    put('etc/kernel-release',(kernel+'\n').encode(),stat.S_IFREG|0o444)
    put('etc/module-order',('\n'.join(order)+'\n').encode(),stat.S_IFREG|0o444)
    for name,record in modules.items():put('modules/'+name+'.ko',lzma.decompress((ROOT/record['path']).read_bytes()),stat.S_IFREG|0o444)
    return files,{'kernel_release':kernel,'sources':sources,'modules':modules,'module_order':order}

def build():
    # Future coordinated assembly only; no runtime tree enters this archive.
    expected=json.loads((OUT/'root-source.json').read_text())
    build_id,identity=source.source_identity()
    if expected['build_id']!=build_id or expected['identity']!=identity:raise ValueError('Root source identity changed')
    files,inputs=prepare_files(build_id)
    raw=b''.join(fs.archive.entry(name,data,mode,i+1,major,minor) for i,(name,(data,mode,major,minor)) in enumerate(sorted(files.items())))
    raw+=fs.archive.entry('TRAILER!!!',b'',0,len(files)+1);raw+=b'\0'*(-len(raw)%512)
    data=gzip.compress(raw,compresslevel=1,mtime=0)
    with (OUT/'bootstrap.cpio.gz').open('xb') as stream:stream.write(data)
    result=dict(inputs,build_id=build_id,initramfs_sha256=fs.sha(data),initramfs_bytes=len(data),uncompressed_bytes=len(raw),entries=fs.archive.inspect(raw),boot_tested=False)
    with (OUT/'bootstrap.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    return result
