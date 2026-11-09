#!/usr/bin/env python3
"""Assemble a fresh minimal test runtime from trusted extracted packages and host libraries.

Input directory contains root/ and packages.json; output minimal-runtime must not exist.
Uses ldd on the trusted QEMU executable. Never downloads or installs.
"""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
base=parser.parse_args().directory.resolve(strict=True)
source=base/'root';out=base/'minimal-runtime';out.mkdir(mode=0o700)
paths={};lib=out/'usr/lib/x86_64-linux-gnu';lib.mkdir(parents=True)
env={**os.environ,'LD_LIBRARY_PATH':str(source/'usr/lib/x86_64-linux-gnu')}
listing=subprocess.check_output(['ldd',str(source/'usr/bin/qemu-system-x86_64')],env=env,text=True)
assert 'not found' not in listing
for raw in re.findall(r'(?:=>\s+)?(/\S+)\s+\(',listing):
 p=Path(raw);dest=lib/p.name
 shutil.copyfile(p,dest);dest.chmod(p.stat().st_mode & 0o777);paths[str(dest.relative_to(out))]=str(p.resolve())
for rel in ['usr/bin/qemu-system-x86_64','usr/share/seabios/bios-256k.bin']:
 p=source/rel;dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);paths[rel]=str(p)
kernels=list((source/'boot').glob('vmlinuz-*'));assert len(kernels)==1
(out/'boot').mkdir();shutil.copy2(kernels[0],out/'boot'/kernels[0].name);paths['boot/'+kernels[0].name]=str(kernels[0])
shutil.copytree(source/'usr/share/qemu',out/'usr/share/qemu',symlinks=True)
records={}
for p in sorted(out.rglob('*')):
 if p.is_symlink():records[str(p.relative_to(out))]={'kind':'symlink','target':os.readlink(p)}
 elif p.is_file():records[str(p.relative_to(out))]={'kind':'file','mode':p.stat().st_mode & 0o777,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(base/'minimal-runtime.lock.json').write_text(json.dumps({'scope':'Fresh official Debian QEMU/kernel with copied pinned host shared libraries; independent minimal test runtime','files':records},indent=2)+'\n')
(base/'minimal-runtime-provenance.json').write_text(json.dumps({'copied_inputs':paths,'ldd':listing,'packages_receipt_sha256':hashlib.sha256((base/'packages.json').read_bytes()).hexdigest()},indent=2)+'\n')
print('Runtime entries:',len(records))
