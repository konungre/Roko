#!/usr/bin/env python3
"""New controller-on-ext4 guest; never rebuild or overwrite the released base userland."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'build/cognitive-filesystem-guest'
BASE=ROOT/'boot/artifacts/roko-persistence-tested.cpio.gz'
BASE_MANIFEST=ROOT/'boot/artifacts/persistence-build-manifest.json'
BASE_SHA256='8021629f1927dc0e33eea3887dd1a34810e22a5f3cafc2aa2e9e9f54841ff111'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
fs=module('cognitive_ext4_builder',ROOT/'boot/filesystem-guest/build.py')
archive=fs.archive
vm=fs.vm
def sha(data): return hashlib.sha256(data).hexdigest()
def inputs(): return fs.inputs()

def unpack(raw):
    archive.inspect(raw)
    result={}; offset=0
    while True:
        values=[int(raw[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        mode,size,nlen=values[1],values[6],values[11]
        offset+=110; name=raw[offset:offset+nlen-1].decode(); offset+=nlen; offset+=-offset%4
        data=raw[offset:offset+size]; offset+=size; offset+=-offset%4
        if name=='TRAILER!!!': break
        if name.startswith('/') or '..' in name.split('/'): raise ValueError('Unsafe archive path')
        result[name]=(data,mode,values[9],values[10])
    return result

CONTROLLER={'scripts/roko.py':'opt/roko/scripts/roko.py',
            'adapters/working_state.py':'opt/roko/adapters/working_state.py',
            'adapters/state_store.py':'opt/roko/adapters/state_store.py',
            'adapters/package_inventory.py':'opt/roko/adapters/package_inventory.py',
            'adapters/avatar_events.py':'opt/roko/adapters/avatar_events.py'}

def build():
    assets,kernel,_,modules,order,sources=inputs()
    base=BASE.read_bytes(); manifest=json.loads(BASE_MANIFEST.read_text())
    if sha(base)!=BASE_SHA256 or manifest['initramfs_sha256']!=BASE_SHA256 or not manifest.get('userland_included'):
        raise ValueError('Released real userland differs from pinned base')
    raw=gzip.decompress(base)
    if archive.inspect(raw)!=manifest['entries']: raise ValueError('Base archive entries mismatch')
    files=unpack(raw)
    for name in ['opt/roko/python/bin/python3.12','opt/roko/adapters/state_store.py','opt/roko/scripts/roko.py','bin/busybox']:
        if name not in files: raise ValueError('Missing genuine userland: '+name)
    def put(name,data,mode=0o444): files[name]=(data,stat.S_IFREG|mode,0,0)
    controller={}
    for source,dest in CONTROLLER.items():
        data=(ROOT/source).read_bytes(); controller[source]=sha(data); put(dest,data)
    scripts={name:sha((HERE/name).read_bytes()) for name in ['build.py','check.py','init.sh']}
    identity={'sources':sources,'modules':modules,'scripts':scripts,'controller':controller,
              'base_archive_sha256':BASE_SHA256,'base_manifest_sha256':sha(BASE_MANIFEST.read_bytes())}
    build_id=sha(json.dumps(identity,sort_keys=True).encode())
    put('init',(HERE/'init.sh').read_bytes(),0o755)
    put('opt/roko/ext4-check.py',(HERE/'check.py').read_bytes())
    put('etc/probe-id',(build_id+'\n').encode())
    put('etc/kernel-release',(kernel+'\n').encode())
    put('etc/module-order',('\n'.join(order)+'\n').encode())
    for name in ['modules','data']: files[name]=(b'',stat.S_IFDIR|0o755,0,0)
    for name,record in modules.items():
        import lzma
        put('modules/'+name+'.ko',lzma.decompress((ROOT/record['path']).read_bytes()))
    raw=b''.join(archive.entry(name,data,mode,i+1,major,minor) for i,(name,(data,mode,major,minor)) in enumerate(sorted(files.items())))
    raw+=archive.entry('TRAILER!!!',b'',0,len(files)+1); raw+=b'\0'*(-len(raw)%512)
    data=gzip.compress(raw,compresslevel=1,mtime=0)
    result=dict(identity,build_id=build_id,kernel_release=kernel,module_order=order,entries=archive.inspect(raw),initramfs_sha256=sha(data),boot_tested=False,
                scope='Genuine StateStore CLI on private ext4, two-boot synthetic evidence; no inference/autonomy/action dispatch')
    OUT.mkdir(mode=0o700,exist_ok=True)
    if OUT.is_symlink() or stat.S_IMODE(OUT.stat().st_mode)!=0o700: raise ValueError('Output directory must be private')
    (OUT/'controller.cpio.gz').write_bytes(data); (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return {k:result[k] for k in ['build_id','initramfs_sha256','base_archive_sha256','scope']}
if __name__=='__main__': print(json.dumps(build(),indent=2))
