"""Map inherited guest BusyBox/kernel inputs without executing archives."""
import hashlib,json,pathlib,re,subprocess,tarfile
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def records(t):
 for b in t.split('\n\n'):
  d={};k=None
  for l in b.splitlines():
   if l.startswith(' ') and k:d[k]+='\n'+l[1:]
   elif ':' in l:k,v=l.split(':',1);d[k]=v.strip()
  if d:yield d
m=json.loads((R/'build/egl-probe/manifest.json').read_text());old=json.loads((R/'boot/tooling-packages.lock.json').read_text()); pkgs=[]
for p in old['packages']:
 if p['package'] not in ['busybox-static','linux-image-6.12.115+deb13.1-amd64']:continue
 archive=R/p['file'];assert sha(archive)==p['sha256'];wanted={k.removeprefix('boot/tooling/root/'):v for k,v in m['sources'].items() if k.startswith('boot/tooling/root/')};matches=[]
 proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(archive)],stdout=subprocess.PIPE)
 with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
  for member in t:
   name=member.name.removeprefix('./')
   if member.isfile() and name in wanted:
    h=hashlib.sha256(t.extractfile(member).read()).hexdigest();assert h==wanted[name];matches.append({'path':name,'sha256':h})
 assert proc.wait()==0
 pkgs.append(dict(p,verified_guest_files=matches))
source_records=[]
for path in (R/'boot/tooling/lists').glob('*_Sources'):
 repo='debian-security' if 'debian-security' in path.name else 'debian'
 for d in records(path.read_text()):
  if (d.get('Package'),d.get('Version')) not in [('busybox','1:1.37.0-6'),('linux-signed-amd64','6.12.115+2'),('linux','6.12.115-2')]:continue
  files=[]
  for l in d['Checksums-Sha256'].strip().splitlines():
   h,n,fn=l.split();files.append({'filename':fn,'sha256':h,'bytes':int(n),'url':f"https://snapshot.debian.org/archive/{repo}/20261103T013555Z/{d['Directory']}/{fn}"})
  source_records.append({'package':d['Package'],'version':d['Version'],'build_depends':d.get('Build-Depends'),'build_depends_arch':d.get('Build-Depends-Arch'),'files':files,'archive_set':'egl-sources' if d['Package']=='busybox' else 'kernel-sources'})
report={'scope':'Inherited EGL guest inputs, distinct from stage runtime_sources.','packages':pkgs,'source_records':source_records,'kernel_status':'Kernel/modules map to linux-signed-amd64 source; its build dependencies point to linux unsigned binaries. Both linux-signed-amd64 and underlying linux source records are provided; kernel-source-bundle.manifest.json records separately acquired archive verification. No complete legal closure claim.','busybox_status':'Exact guest BusyBox binary verified against existing official .deb; three source files reused and independently checksum-verified in EGL source bundle.','qemu_status':'Two qemu plugin paths in guest manifest sources are host test inputs, not guest payload source obligations.'}
(O/'inherited-guest-source-map.json').write_text(json.dumps(report,indent=2)+'\n');print([(p['package'],len(p['verified_guest_files'])) for p in pkgs]);print([(p['package'],p['version'],sum(f['bytes'] for f in p['files'])) for p in source_records])
