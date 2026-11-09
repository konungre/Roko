#!/usr/bin/env python3
"""Explicitly acquire pinned official Debian packages into workspace only; never host-install."""
import argparse,hashlib,json,os,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'boot/tooling'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--download',action='store_true',help='Explicitly download missing pinned packages');args=p.parse_args()
 lock=json.loads((ROOT/'boot/tooling-packages.lock.json').read_text())
 (T/'archives').mkdir(parents=True,exist_ok=True);target=T/'root';target.mkdir(exist_ok=True)
 for package in lock['packages']:
  relative=Path(package['file'])
  if relative.is_absolute() or '..' in relative.parts or relative.parts[:3]!=('boot','tooling','archives') or relative.suffix!='.deb':raise SystemExit('Unsafe package path')
  if not package['download_url'].startswith(('https://snapshot.debian.org/archive/debian/20261103T013555Z/pool/','https://snapshot.debian.org/archive/debian-security/20261103T013555Z/pool/')):raise SystemExit('Unexpected package origin')
  path=ROOT/relative
  if not path.is_file():
   if not args.download:raise SystemExit('Missing '+str(path)+'; explicit --download required')
   temp=path.with_suffix('.partial')
   with urllib.request.urlopen(package['download_url'],timeout=90) as source,temp.open('wb') as sink:
    while True:
     chunk=source.read(1024*1024)
     if not chunk:break
     sink.write(chunk)
   if hashlib.sha256(temp.read_bytes()).hexdigest()!=package['sha256']:raise SystemExit('Download hash mismatch; refusing extraction')
   os.replace(temp,path)
  if hashlib.sha256(path.read_bytes()).hexdigest()!=package['sha256']:raise SystemExit('Package hash mismatch: '+str(path))
  subprocess.run(['dpkg-deb','-x',str(path),str(target)],check=True,timeout=120)
 # The launcher locates this runtime relative to its own project path.
 assets=json.loads((ROOT/'boot/boot-assets.lock.json').read_text())
 for kind,relative in [('kernel','boot/tooling/root/boot/vmlinuz-6.12.115+deb13.1-amd64'),('qemu','boot/launch-qemu.sh'),('busybox','boot/tooling/root/usr/bin/busybox')]:
  path=ROOT/relative;expected=lock['important_files'][relative]
  if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise SystemExit('Extracted asset mismatch')
  assets[kind]={'path':str(path),'sha256':expected}
 (ROOT/'boot/boot-assets.lock.json').write_text(json.dumps(assets,indent=2)+'\n')
 print('Verified/extracted '+str(len(lock['packages']))+' pinned packages. No host installation or maintainer scripts ran.')
if __name__=='__main__':main()
