#!/usr/bin/env python3
"""Stream a separate persistent desktop derivative. Requires an exact coordinated base ID."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=ROOT/'build/basilisk-avatar-guest'
OUT=ROOT/'build/cosmic-persistent-guest'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
avatar=load('persistent_avatar_archive',ROOT/'boot/basilisk-avatar-guest/build.py')
storage=load('persistent_storage_overlay',ROOT/'boot/desktop-filesystem-guest/overlay.py')
def sha(data): return hashlib.sha256(data).hexdigest()
def file_sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def build(expected_base_id):
    raw_manifest=(BASE/'manifest.json').read_bytes(); base=json.loads(raw_manifest)
    source=BASE/'avatar.cpio.gz'
    if len(expected_base_id)!=64 or base['build_id']!=expected_base_id or file_sha(source)!=base['initramfs_sha256']:
        raise ValueError('Coordinated avatar base changed')
    # Read only the required entries first, validating their actual archived bytes.
    selected={}
    for name,data,mode,major,minor in avatar.read_archive(source):
        if name in ('init','usr/share/applications/roko.desktop','usr/bin/roko-console-fixture'):
            record=base['entries'].get(name,{})
            if record.get('sha256')!=sha(data) or record.get('mode')!=mode: raise ValueError('Base hook entry changed')
            selected[name]=(data,mode,major,minor)
        if len(selected)==3: break
    if len(selected)!=3: raise ValueError('Missing genuine desktop/init hooks')
    files,provenance=storage.prepare(selected['usr/share/applications/roko.desktop'][0],selected['usr/bin/roko-console-fixture'][0])
    init=storage.derive_init(selected['init'][0])
    files['init']=(init,*selected['init'][1:])
    provenance['init_before_sha256']=sha(selected['init'][0]);provenance['init_after_sha256']=sha(init)
    identity={'base_build_id':expected_base_id,'base_initramfs_sha256':base['initramfs_sha256'],
              'base_manifest_sha256':sha(raw_manifest),'storage':provenance,'builder_sha256':sha(Path(__file__).read_bytes()),
              'archive_reader_sha256':sha((ROOT/'boot/basilisk-avatar-guest/build.py').read_bytes()),
              'module_inputs_builder_sha256':sha((ROOT/'boot/filesystem-guest/build.py').read_bytes())}
    build_id=sha(json.dumps(identity,sort_keys=True).encode())
    files['etc/storage-probe-id']=((build_id+'\n').encode(),stat.S_IFREG|0o444,0,0)
    OUT.mkdir(mode=0o700,exist_ok=True)
    if OUT.is_symlink() or stat.S_IMODE(OUT.stat().st_mode)!=0o700: raise ValueError('Expected private output directory')
    archive=OUT/'persistent.cpio.gz'; entries={}; seen=set(); replaced={}; ino=0;total=0
    with archive.open('xb') as destination:
        with gzip.GzipFile(fileobj=destination,mode='wb',filename='',mtime=0,compresslevel=1) as output:
            def emit(name,data,mode,major=0,minor=0):
                nonlocal ino,total
                if name in entries: raise ValueError('Duplicate derived archive entry')
                ino+=1;blob=avatar.record(name,data,mode,ino,major,minor);output.write(blob);total+=len(blob)
                entries[name]={'mode':mode,'bytes':len(data),'sha256':sha(data),'uid':0,'gid':0,'mtime':0,'rdevmajor':major,'rdevminor':minor}
            for name,data,mode,major,minor in avatar.read_archive(source):
                expected=base['entries'].get(name,{})
                if expected.get('sha256')!=sha(data) or expected.get('mode')!=mode or expected.get('rdevmajor',0)!=major or expected.get('rdevminor',0)!=minor:
                    raise ValueError('Changed base entry: '+name)
                seen.add(name)
                if name in files:
                    updated=files.pop(name)
                    if updated!=(data,mode,major,minor):
                        if name not in ('init','usr/share/applications/roko.desktop','usr/bin/roko-console-fixture'): raise ValueError('Unexpected overlay collision: '+name)
                        replaced[name]={'before_sha256':sha(data),'after_sha256':sha(updated[0])}
                    data,mode,major,minor=updated
                emit(name,data,mode,major,minor)
            if seen!=set(base['entries']): raise ValueError('Base entry set differs')
            for name in list(files):
                for parent in Path(name).parents:
                    key=str(parent)
                    if key!='.' and key not in entries: files.setdefault(key,(b'',stat.S_IFDIR|0o755,0,0))
            for name,value in sorted(files.items()): emit(name,*value)
            trailer=avatar.record('TRAILER!!!',b'',0,ino+1); output.write(trailer);output.write(b'\0'*(-(total+len(trailer))%512))
    result=dict(identity,build_id=build_id,explicit_replacements=replaced,entries=entries,initramfs_sha256=file_sha(archive),initramfs_bytes=archive.stat().st_size,boot_tested=False,
                scope='Separate genuine avatar/desktop with private ext4 StateStore; no host disk, network or autonomy')
    with (OUT/'manifest.json').open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    return {k:result[k] for k in ['build_id','base_build_id','initramfs_sha256','boot_tested']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--base-build-id');a=p.parse_args()
    if a.build:
        if not a.base_build_id: p.error('--build requires coordinated --base-build-id')
        print(json.dumps(build(a.base_build_id),indent=2))
    else: print('No image assembled; explicit --build and exact base identity required')
