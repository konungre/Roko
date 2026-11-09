#!/usr/bin/env python3
"""Record downloaded Debian packages and compare each SHA-256 to signed apt metadata."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'boot/tooling'
env={**os.environ,'APT_CONFIG':str(T/'apt.conf')}
packages=[]
for file in sorted((T/'archives').glob('*.deb')):
 fields=subprocess.check_output(['dpkg-deb','-f',str(file),'Package','Version','Architecture','Source'],text=True)
 meta=dict(line.split(': ',1) for line in fields.splitlines() if ': ' in line)
 packages.append({'package':meta['Package'],'version':meta['Version'],'architecture':meta['Architecture'],'source':meta.get('Source',meta['Package']),'file':str(file.relative_to(ROOT)),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
specs=[p['package']+'='+p['version'] for p in packages]
raw=subprocess.check_output(['apt-cache','show',*specs],env=env,text=True)
index={}
for para in raw.split('\n\n'):
 fields={}
 for line in para.splitlines():
  if line and not line.startswith((' ','\t')) and ': ' in line:
   k,v=line.split(': ',1);fields[k]=v
 if all(k in fields for k in ['Package','Version','Architecture','SHA256','Filename']):
  index[(fields['Package'],fields['Version'],fields['Architecture'])]=fields
for p in packages:
 metadata=index[(p['package'],p['version'],p['architecture'])]
 assert metadata['SHA256']==p['sha256'],p['package']
 p['repository_filename']=metadata['Filename']
 origin='debian-security' if metadata['Filename'].startswith('pool/updates/') else 'debian'
 p['download_url']='https://snapshot.debian.org/archive/'+origin+'/20261103T013555Z/'+metadata['Filename']
important={}
for rel in ['boot/tooling/root/usr/bin/qemu-system-x86_64','boot/tooling/root/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2','boot/tooling/root/usr/share/seabios/bios-256k.bin','boot/tooling/root/boot/vmlinuz-6.12.115+deb13.1-amd64','boot/launch-qemu.sh','boot/tooling/root/usr/bin/busybox']:
 important[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
report={'origin':'Official signed Debian snapshot metadata at 20261103T013555Z','verification':'apt update verified signed InRelease using Debian archive keyring; every deb SHA-256 matched cached package metadata','scope':'Workspace-only download and extraction; no maintainer scripts or host installation','packages':packages,'important_files':important,'package_count':len(packages)}
(ROOT/'boot/tooling-packages.lock.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'packages':len(packages),'all_metadata_hashes_match':True,'important_files':important},indent=2))
