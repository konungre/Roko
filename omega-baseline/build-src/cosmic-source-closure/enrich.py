import hashlib,json,pathlib,subprocess,tarfile
R=pathlib.Path(__file__).resolve().parents[2];S=R/'build-src/cosmic-comp-stage';O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((O/'inventory.json').read_text()); signatures=[]
for repo,suite,short in [('debian','trixie','debian'),('debian-security','trixie-security','security')]:
 src=R/f'boot/tooling/lists/snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_InRelease'; out=O/f'{short}-Release.verified'
 if out.exists():out.unlink()
 cmd=['sqv','--keyring','/usr/share/keyrings/debian-archive-keyring.gpg','--output',str(out),'--cleartext',str(src)]
 p=subprocess.run(cmd,capture_output=True,text=True);same=p.returncode==0 and sha(out)==sha(S/f'apt/{short}-Release.verified');signatures.append({'inrelease':str(src.relative_to(R)),'inrelease_sha256':sha(src),'verified':same,'signers':p.stdout.splitlines(),'stderr':p.stderr,'command':cmd})
 assert same
owners={}
cache=O/'archive-ownership.json'
cache_lock=O/'archive-ownership-lock.sha256'
lock_hash=sha(S/'debian-packages.lock.json')
if cache.exists() and cache_lock.exists() and cache_lock.read_text().strip()==lock_hash:owners=json.loads(cache.read_text())
else:
 for pkg in d['debian_packages']:
  archive=S/'apt/archives'/pathlib.Path(pkg['filename']).name;assert sha(archive)==pkg['sha256']
  p=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(archive)],stdout=subprocess.PIPE)
  with tarfile.open(fileobj=p.stdout,mode='r|') as t:
   for m in t:
    if m.isfile() or m.issym() or m.islnk():owners.setdefault(m.name.removeprefix('./'),[]).append(pkg['package'])
  assert p.wait()==0
 cache.write_text(json.dumps(owners,indent=2)+'\n')
 cache_lock.write_text(lock_hash+'\n')
selections=[]
for path in [R/'build/egl-probe/manifest.json',R/'build/cosmic-guest/manifest.json']:
 if not path.exists():continue
 m=json.loads(path.read_text());rows=[]
 for name,h in m.get('runtime_sources',{}).items():
  f=S/'sysroot'/name
  with f.open('rb') as stream:magic=stream.read(4)
  role='notice' if name.startswith('usr/share/doc/') else ('runtime_elf' if magic==b'\x7fELF' else 'runtime_data')
  rows.append({'sysroot_path':name,'sha256':h,'matches_staged_file':sha(f)==h,'debian_packages':owners.get(name,[]),'role':role})
 used=sorted({p for r in rows if r['role']!='notice' for p in r['debian_packages']})
 notice=sorted({p for r in rows if r['role']=='notice' for p in r['debian_packages']})
 notice_only=sorted(set(notice)-set(used));selected=[p for p in d['debian_packages'] if p['package'] in used]
 files={f['url']:f for p in selected for f in p['corresponding_source_files']}
 notice_files={f['url']:f for p in d['debian_packages'] if p['package'] in notice_only for f in p['corresponding_source_files']}
 selections.append({'manifest':str(path.relative_to(R)),'manifest_sha256':sha(path),'artifact_bindings':{k:m[k] for k in ['build_id','initramfs_sha256','compositor_commit','compositor_sha256','client_sha256','compositor_runtime_data','scripts'] if k in m},'runtime_files':rows,'packages':used,'notice_packages':notice,'notice_only_packages':notice_only,'classification':'usr/share/doc/* is notice evidence; other ELF magic files are runtime_elf; remaining non-notice files runtime_data. Notice-only means no selected runtime ELF/data owned by that package.','source_archives':list(files.values()),'source_download_bytes':sum(f['bytes'] for f in files.values()),'notice_only_source_archives':list(notice_files.values()),'notice_only_source_download_bytes':sum(f['bytes'] for u,f in notice_files.items() if u not in files),'unmapped_runtime_files':[r['sysroot_path'] for r in rows if r['role']!='notice' and not r['debian_packages']],'other_guest_sources':m.get('sources',m.get('graphics_sources',{})),'scope':'Only non-notice runtime_sources count toward staged Debian runtime ELF/data source closure; notice-only provenance separate. Kernel/modules/BusyBox/own binaries separately mapped.'})
d['signature_reverification']=signatures;d['guest_selections']=selections
(O/'inventory.json').write_text(json.dumps(d,indent=2)+'\n')
s=json.loads((R/'boot/cosmic-source-closure.json').read_text());s['inventory_sha256']=sha(O/'inventory.json');s['missing_rust_license_declarations']=[p['name'] for p in d['rust_packages'] if not p.get('license') and not p.get('license_file')];s['signature_reverification_passed']=all(x['verified'] for x in signatures);s['guest_selections']=[{k:v for k,v in x.items() if k in ['manifest','manifest_sha256','artifact_bindings','packages','notice_only_packages','notice_only_source_download_bytes','classification','source_download_bytes','unmapped_runtime_files','scope']} for x in selections]
s['status']='available_guest_subset_mapped_cosmic_pending' if not (R/'build/cosmic-guest/manifest.json').exists() else 'cosmic_guest_runtime_subset_mapped'
(R/'boot/cosmic-source-closure.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
