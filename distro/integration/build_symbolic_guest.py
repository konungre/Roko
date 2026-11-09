#!/usr/bin/env python3
"""Build a fresh minimal guest from a verified LOCAL symbolic runtime.

Trusted local runtime only: ldd is used on its native objects. No ISO or model.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from build_probe import baseline, FLAGS


def build(runtime, output):
    runtime=Path(runtime).resolve(strict=True);output=Path(output)
    profile=json.loads((runtime/'symbolic-profile.json').read_text())
    for name,expected in profile['files'].items():
        with Path(name).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Local runtime changed: '+name)
    output.mkdir(mode=0o700)
    stage=output/'root';stage.mkdir()
    app=stage/'opt/roko';app.mkdir(parents=True)
    ignored=shutil.ignore_patterns('.git','__pycache__','*.pyc','site-packages','test','tests','ensurepip','tkinter','_tkinter*','idlelib','turtledemo')
    shutil.copytree(runtime/'swipl',app/'swipl',symlinks=False,ignore=ignored)
    for name in ('petta','omega'):shutil.copytree(runtime/name,app/name,symlinks=False,ignore=ignored)
    python=Path(profile['python']).resolve();pyhome=Path(profile['runtime_env']['PYTHONHOME'])
    (app/'python/bin').mkdir(parents=True);shutil.copy2(python,app/'python/bin/python3.12')
    shutil.copytree(pyhome/'lib/python3.12',app/'python/lib/python3.12',symlinks=False,ignore=ignored)
    for p in (pyhome/'lib').glob('libpython3.12.so*'):shutil.copy2(p,app/'python/lib'/p.name)
    shutil.copytree(runtime/'venv/lib/python3.12/site-packages/yaml',app/'site-packages/yaml',ignore=ignored)
    shutil.copy2(HERE.parents[1]/'omega-baseline/scripts/no-network.py',app/'no-network.py')
    probe=(runtime/'probe.pl').read_text().replace(str(runtime/'petta'),'/opt/roko/petta').replace(str(runtime/'omega'),'/opt/roko/omega')
    probe=probe.replace(' use_module(library(janus)),',' use_module(library(janus)),\n py_call(os:getuid(), 1000), py_call(os:getgid(), 1000),')
    (app/'probe.pl').write_text(probe)
    libraries=stage/'usr/lib/x86_64-linux-gnu';libraries.mkdir(parents=True)
    native=[]
    for p in app.rglob('*'):
        if p.is_file():
            with p.open('rb') as f:
                if f.read(4)==b'\x7fELF':native.append(p)
    provenance={}
    env={**os.environ,'LD_LIBRARY_PATH':str(app/'python/lib')+':'+str(app/'swipl/lib/swipl/lib/x86_64-linux')}
    for p in native:
        result=subprocess.run(['ldd',str(p)],env=env,capture_output=True,text=True,timeout=10)
        if result.returncode or 'not found' in result.stdout:raise ValueError('Unresolved native dependency: '+str(p)+' '+result.stdout)
        for name in re.findall(r'(?:=>\s+)?(/\S+)\s+\(',result.stdout):
            src=Path(name)
            if src.is_relative_to(stage):continue
            dest=libraries/src.name
            if not dest.exists():shutil.copy2(src,dest);provenance[str(dest.relative_to(stage))]=str(src.resolve())
    # The child-only network filter loads this library at runtime.
    shutil.copy2('/usr/lib/x86_64-linux-gnu/libseccomp.so.2',libraries/'libseccomp.so.2')
    (stage/'lib64').mkdir();shutil.copy2(libraries/'ld-linux-x86-64.so.2',stage/'lib64/ld-linux-x86-64.so.2')
    for directory in ('dev','proc','sys','tmp','home/roko'):(stage/directory).mkdir(parents=True,exist_ok=True)
    (stage/'tmp').chmod(0o1777)
    source=(HERE/'symbolic_init.c').read_bytes()
    identity=hashlib.sha256(source+(runtime/'symbolic-profile.json').read_bytes()).hexdigest()
    subprocess.run(['gcc',*FLAGS,'-DROKO_BUILD_ID="'+identity+'"',str(HERE/'symbolic_init.c'),'-o',str(output/'init')],check=True,timeout=60)
    shutil.copy2(output/'init',stage/'init')
    records=[];entries={}
    for i,p in enumerate(sorted(stage.rglob('*')),1):
        name=str(p.relative_to(stage));info=p.stat()
        # Host staging is private; guest immutable runtime must be traversable/readable by UID1000.
        mode=(stat.S_IFDIR|0o755) if p.is_dir() else (stat.S_IFREG|(0o555 if info.st_mode & 0o111 else 0o444))
        if name=='tmp':mode=stat.S_IFDIR|0o1777
        if name=='home/roko':mode=stat.S_IFDIR|0o700
        data=b'' if p.is_dir() else p.read_bytes()
        entry=baseline.entry(name,data,mode,i)
        if name=='home/roko':entry=entry[:22]+b'000003e8000003e8'+entry[38:]
        records.append(entry)
    for name,major,minor,mode in [('console',5,1,0o600),('null',1,3,0o666),('zero',1,5,0o666),('urandom',1,9,0o666)]:
        records.append(baseline.entry('dev/'+name,b'',stat.S_IFCHR|mode,len(records)+1,major,minor))
    records.append(baseline.entry('TRAILER!!!',b'',0,len(records)+1))
    raw=b''.join(records);raw+=b'\0'*(-len(raw)%512)
    entries=baseline.inspect(raw)
    data=gzip.compress(raw,compresslevel=6,mtime=0);(output/'initramfs.cpio.gz').write_bytes(data)
    report={'schema':'roko-symbolic-guest-build-v1','build_id':identity,'init_sha256':hashlib.sha256((output/'init').read_bytes()).hexdigest(),'initramfs_sha256':hashlib.sha256(data).hexdigest(),'source_sha256':hashlib.sha256(source).hexdigest(),'profile_sha256':hashlib.sha256((runtime/'symbolic-profile.json').read_bytes()).hexdigest(),'entries':entries,'copied_host_libraries':provenance,'guest_tested':False,'model_included':False,'bytes':len(data),'uncompressed_bytes':len(raw)}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return {'entries':len(entries),'bytes':len(data),'uncompressed_bytes':len(raw)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(build(a.runtime,a.output)))
