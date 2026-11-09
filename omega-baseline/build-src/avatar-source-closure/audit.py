"""Read-only avatar/persistent provenance audit; no source fetch/build/install."""
import collections,hashlib,json,pathlib,posixpath,re,shlex,subprocess,tarfile,lzma
R=pathlib.Path(__file__).resolve().parents[2];W=R.parent;O=pathlib.Path(__file__).parent;M=R/'build/basilisk-avatar-guest/manifest.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def record(p):return {'path':str(p.relative_to(W)),'sha256':sha(p)}
def pars(text):
 for b in text.split('\n\n'):
  d={};k=None
  for l in b.splitlines():
   if l.startswith((' ','\t')) and k:d[k]+='\n'+l[1:]
   elif ':' in l:k,v=l.split(':',1);d[k]=v.strip()
  if d:yield d
m=load(M);mh=sha(M);errors=[];warnings=[];checks=[]
# Independently authenticate indexes and compare package/source mappings.
srcs={};bins={}
for repo,suite,short in [('debian','trixie','debian'),('debian-security','trixie-security','security')]:
 ip=R/f'boot/tooling/lists/snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_InRelease';out=O/f'{short}-Release.verified'
 if out.exists():out.unlink()
 cmd=['sqv','--keyring','/usr/share/keyrings/debian-archive-keyring.gpg','--output',str(out),'--cleartext',str(ip)]
 result=subprocess.run(cmd,capture_output=True,text=True);assert result.returncode==0;checks.append({'kind':'signature','file':str(ip.relative_to(R)),'sha256':sha(ip),'signers':result.stdout.splitlines(),'success':True})
 expected={x.split()[2]:x.split()[:2] for x in out.read_text().split('SHA256:\n')[1].split('\nSHA512:')[0].splitlines() if len(x.split())==3}
 for kind,rel in [('Packages','main/binary-amd64/Packages'),('Sources','main/source/Sources')]:
  p=R/f'boot/tooling/lists/snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_{rel.replace("/","_")}'
  assert sha(p)==expected[rel][0] and p.stat().st_size==int(expected[rel][1]);checks.append(dict(record(p),kind='index',success=True))
  for d in pars(p.read_text()):(srcs if kind=='Sources' else bins)[repo,d['Package'],d['Version']]=d
# Historical 0.19 binding and sources remain read-only.
basepath=R/'build/cosmic-session-guest-history/061e179a-passed/manifest.json';base=load(basepath);baseaudit=load(R/'boot/cosmic-session-source-closure.json')
assert m['base_build_id']==base['build_id']==baseaudit['build_id']
assert m['base_initramfs_sha256']==base['initramfs_sha256']==baseaudit['initramfs_sha256']
acceptpath=R/'results/basilisk-avatar-guest/focused-acceptance.json';accept=load(acceptpath)
assert accept['build_id']==m['build_id'] and accept['initramfs_sha256']==m['initramfs_sha256'] and accept['passed']
assert sha(M.parent/'avatar.cpio.gz')==m['initramfs_sha256']
stages={};package_map={};archive_cache=O/'archive-ownership.json';archive_owners=load(archive_cache) if archive_cache.exists() else {}
for name in ['basilisk-stage','basilisk-layer-stage']:
 S=R/'build-src'/name;dp=load(S/'debian-packages.lock.json');owners={}
 for p in dp['packages']:
  repo='debian-security' if '/debian-security/' in p['url'] else 'debian';b=bins[repo,p['package'],p['version']];s=srcs[repo,p['source'],p['source_version']]
  expected={fn:(h,int(z)) for h,z,fn in (x.split() for x in s['Checksums-Sha256'].strip().splitlines())};assert b['SHA256']==p['sha256']
  for f in p['corresponding_source_files']:assert expected[f['filename']]==(f['sha256'],f['bytes'])
  archive=S/'apt/archives'/pathlib.Path(p['filename']).name
  if p['sha256'] not in archive_owners:
   assert sha(archive)==p['sha256'];names=[];proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(archive)],stdout=subprocess.PIPE)
   with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
    for f in t:
     if f.isfile() or f.issym() or f.islnk():names.append(f.name.removeprefix('./'))
   assert proc.wait()==0;archive_owners[p['sha256']]=names
  key=p['package']+'='+p['version'];package_map[key]=p
  for path in archive_owners[p['sha256']]:owners.setdefault(path,[]).append(key)
 stages[name]={'stage':S,'packages':dp,'owners':owners}
archive_cache.write_text(json.dumps(archive_owners,indent=2)+'\n')
def native_path(stage,path):
 root=stage/'sysroot';parts=path.split('/');done=[];n=0
 while parts:
  component=parts.pop(0)
  if component in ('','.'):continue
  if component=='..':
   if done:done.pop()
   else:raise ValueError('Escapes sysroot')
   continue
  p=root.joinpath(*done,component)
  if p.is_symlink():
   n+=1;assert n<50;target=str(p.readlink())
   if target.startswith('/'):done=[]
   parts=target.split('/')+parts
  else:done.append(component)
 return '/'.join(done)
overlays=[];file_rows=[];native_roles=collections.defaultdict(set);generated=[];own=[]
for spec in m['overlays']:
 root=W/spec['root'];lp=W/spec['lock'];assert sha(lp)==spec['lock_sha256'];lock=load(lp)
 files=lock.get('files') if 'files' in lock else [{'path':p,'sha256':h} for p,h in lock.items()]
 assert len(files)==spec['files'];stage_name='basilisk-layer-stage' if 'basilisk-layer-stage' in spec['root'] else 'basilisk-stage'
 st=stages[stage_name];stage=st['stage'];owners=st['owners']
 if lock.get('source_lock_sha256'):assert lock['source_lock_sha256']==sha(stage/'debian-files.lock.json')
 for f in files:
  path=f['path'];local=root/path;assert sha(local)==f['sha256'];retained=m['entries'].get(path,{}).get('sha256')==f['sha256']
  if not retained:role='superseded_overlay_input';pk=[];canonical=None
  else:
   canonical=native_path(stage,path);native=stage/'sysroot'/canonical;pk=owners.get(canonical,[]) if native.is_file() and sha(native)==f['sha256'] else []
   if pk:
    with local.open('rb') as stream:magic=stream.read(4)
    role='notice' if path.startswith('usr/share/doc/') else 'runtime_elf' if magic==b'\x7fELF' else 'runtime_data'
    for key in pk:native_roles[key].add(role)
   elif path.startswith('usr/share/mime/'):
    role='generated_mime_data';pk=[k for k,p in package_map.items() if p['package']=='shared-mime-info'];generated.append(path)
    for key in pk:native_roles[key].add('generated_data_source')
   elif path=='usr/share/glib-2.0/schemas/gschemas.compiled':role='generated_schema_cache';generated.append(path)
   else:role='authored_application_or_data';own.append({'path':path,'source':str(local.relative_to(W)),'sha256':f['sha256']})
  file_rows.append({'path':path,'sha256':f['sha256'],'overlay':spec['root'],'retained_in_image':retained,'role':role,'native_canonical_path':canonical,'owners':pk})
 # Generator inputs verified from lock, not regenerated/executed.
 inputs=[]
 for path,h in lock.get('generator_verified_sources',{}).items():
  canonical=native_path(stage,path);p=stage/'sysroot'/canonical;assert sha(p)==h;pk=owners.get(canonical,[])
  inputs.append({'path':path,'sha256':h,'owners':pk})
  for key in pk:native_roles[key].add('generator_input')
 overlays.append({'spec':spec,'lock':record(lp),'generator_inputs':inputs,'runtime_source_count':len(lock.get('runtime_sources',{})),'hicolor_provenance':lock.get('hicolor_provenance')})
 # Canonical sources cover resolved aliases/dlopen/helper/schema inputs. Only retained bytes count as shipped.
 image_hashes={x.get('sha256') for x in m['entries'].values()}
 for path,h in lock.get('runtime_sources',{}).items():
  p=stage/'sysroot'/path;assert sha(p)==h
  if h in image_hashes:
   role='notice' if path.startswith('usr/share/doc/') else 'runtime_source'
   for key in owners.get(path,[]):native_roles[key].add(role)
actual=sorted(k for k,roles in native_roles.items() if roles-{'notice','generator_input'});notice_only=sorted(k for k,r in native_roles.items() if r=={'notice'});generator_only=sorted(k for k,r in native_roles.items() if r <= {'notice','generator_input'} and 'generator_input' in r)
# Combined image roles: base userland and terminfo remain byte-identical; only authored init changes.
baseinventory=load(R/'build-src/cosmic-session-source-closure/inventory.json')
base_runtime={p['package']+'='+p['version'] for p in baseinventory['runtime_packages']+baseinventory['terminfo_packages']}
base_native_lock=load(R/'build-src/cosmic-desktop-stage/debian-packages.lock.json')
base_notice={p['package']+'='+p['version'] for p in base_native_lock['packages'] if p['package'] in baseinventory['notice_only_packages']}
combined_runtime=sorted(base_runtime|set(actual));combined_notice=sorted((base_notice|set(notice_only))-set(combined_runtime));new_runtime=sorted(set(actual)-base_runtime)
base_changed=[p for p,v in base['entries'].items() if m['entries'].get(p)!=v];assert base_changed==['init']
# Hicolor dataset and package are explicitly bound, separate from authored favorite-list data.
hicolor=load(R/'build-src/cosmic-dock-stage/avatar-v1.lock.json')['hicolor_provenance'];hp=next(p for p in package_map.values() if p['package']=='hicolor-icon-theme')
assert hp['version']==hicolor['version'] and hp['sha256']==hicolor['archive_sha256']
assert m['entries']['usr/share/icons/hicolor/index.theme']['sha256']==hicolor['index_sha256']
# Own art/controller sources are pinned by their exact overlay bytes; identify explicitly, do not download.
art=R/'desktop/basilisk/assets/roko.png';assert sha(art)=='8e2f01b673c60b9fd683754a4278c9ca3de8ceb88e46d8b22944b6da1aa82e23';assert m['entries']['usr/share/roko/basilisk/assets/roko.png']['sha256']==sha(art)
controller_lock=load(R/'build-src/omega-avatar-controller-stage/overlay-v1.lock.json');controller=[]
for src,dest in controller_lock['source_files'].items():
 p=R/src;h=sha(p);assert m['entries'][dest]['sha256']==h;controller.append(dict(record(p),destination=dest))
# Preserve complete baseline source coverage; new sources are deduplicated against already verified sets.
sourcefiles={};selected=[]
for key in actual+generator_only:
 p=package_map[key];copyright=stages['basilisk-layer-stage']['stage']/'sysroot/usr/share/doc'/p['package']/'copyright'
 if not copyright.exists():copyright=stages['basilisk-stage']['stage']/'sysroot/usr/share/doc'/p['package']/'copyright'
 selected.append(dict(p,roles=sorted(native_roles[key]),copyright=dict(record(copyright),debian_license_labels=sorted(set(re.findall(r'^License: (.+)',copyright.read_text(errors='replace'),re.M)))) if copyright.is_file() else None))
 for f in p['corresponding_source_files']:sourcefiles[f['sha256']]=f
acquired={};successful_transfer=0
for p in (R/'build-src/cosmic-source-closure').glob('*source-bundle.manifest.json'):
 d=load(p);successful_transfer+=d['downloaded_bytes']
 for f in d['files']:assert sha(R/f['local_path'])==f['sha256'];acquired[f['sha256']]=f
p=R/'build-src/cosmic-session-source-closure/acquired-native-sources.json';d=load(p);successful_transfer+=sum(f['bytes'] for f in d['files'])
for f in d['files']:assert sha(R/f['local_path'])==f['sha256'];acquired[f['sha256']]=f
new_acquisition=O/'acquired-sources.json'
if new_acquisition.exists():
 for f in load(new_acquisition)['files']:
  assert sha(R/f['path'])==f['sha256'];acquired[f['sha256']]=f
missing=[f for h,f in sourcefiles.items() if h not in acquired];needed=sum(f['bytes'] for f in missing);assert successful_transfer==749926294
# Prior interrupted initial pass was not byte-metered. Budget conservatively charges a full session plan twice.
conservative_prior=successful_transfer+119486927
(O/'missing-native-sources.json').write_text(json.dumps(missing,indent=2)+'\n')
# Source/schema generation recipe: retain exact source XML and compiler inputs, do not regenerate.
schema_inputs=[r for r in file_rows if r['retained_in_image'] and (r['path'].startswith('usr/share/glib-2.0/schemas/') or 'glib-compile-schemas' in r['path'])]
recipes=[record(R/p) for p in ['boot/basilisk-guest/prepare_overlay.py','boot/basilisk-guest/prepare_mime_overlay.py','boot/basilisk-guest/prepare_gio_overlay.py','boot/basilisk-guest/prepare_layer_overlay.py','boot/basilisk-guest/prepare_controller_overlay.py','boot/basilisk-avatar-guest/build.py']]
authored_sources=[]
for f in own:
 dest=f['path'];suffix=dest.removeprefix('usr/share/roko/basilisk/')
 candidate=W/'roko-basilisk'/suffix if dest.startswith('usr/share/roko/basilisk/') else None
 if candidate and candidate.is_file() and sha(candidate)==f['sha256']:authored_sources.append(dict(record(candidate),destination=dest))
for name,h in m['scripts'].items():
 p=R/'boot/basilisk-avatar-guest'/name;assert sha(p)==h;authored_sources.append(dict(record(p),role='authored_guest_script'))
assert m['derived_init']['base_sha256']==base['entries']['init']['sha256'] and m['derived_init']['derived_sha256']==m['entries']['init']['sha256']
# Persistent derived image: verify bytes/module origin only; no boot-pass claim.
P=R/'build/cosmic-persistent-guest/manifest.json';pm=load(P);assert pm['base_build_id']==m['build_id'] and pm['base_manifest_sha256']==mh and pm['base_initramfs_sha256']==m['initramfs_sha256'];persistent_modules=[]
for name,info in pm['storage']['modules'].items():
 p=R/info['path'];assert sha(p)==info['sha256'];assert hashlib.sha256(lzma.decompress(p.read_bytes())).hexdigest()==info['decompressed_sha256'];persistent_modules.append({'name':name,**info})
# Verify these compressed module bytes inside the original signed Debian kernel package.
kp=next(p for p in load(R/'boot/tooling-packages.lock.json')['packages'] if p['package']=='linux-image-6.12.115+deb13.1-amd64');assert sha(R/kp['file'])==kp['sha256'];wanted={x['path'].removeprefix('boot/tooling/root/'):x['sha256'] for x in persistent_modules};matched=[]
proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(R/kp['file'])],stdout=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
 for f in t:
  name=f.name.removeprefix('./')
  if f.isfile() and name in wanted:assert hashlib.sha256(t.extractfile(f).read()).hexdigest()==wanted[name];matched.append(name)
assert proc.wait()==0 and len(matched)==len(wanted)
persistent_authored=[]
for name,h in pm['storage']['scripts'].items():
 p=R/'boot/desktop-filesystem-guest'/name;assert sha(p)==h;persistent_authored.append(record(p))
assert sha(R/'boot/cosmic-persistent-guest/build.py')==pm['builder_sha256']
assert sha(R/'boot/basilisk-avatar-guest/build.py')==pm['archive_reader_sha256']
assert sha(R/'boot/filesystem-guest/build.py')==pm['module_inputs_builder_sha256']
images=list(P.parent.glob('*.cpio.gz'));assert len(images)==1 and sha(images[0])==pm['initramfs_sha256']
changed={p:{'before':m['entries'].get(p),'after':v} for p,v in pm['entries'].items() if m['entries'].get(p)!=v}
report={'schema':1,'scope':'Stable avatar/controller overlay provenance plus separate unproven persistent derivative. No compliance, inference/autonomy or full-desktop claim.','avatar_manifest':record(M),'build_id':m['build_id'],'initramfs_sha256':m['initramfs_sha256'],'focused_acceptance':record(acceptpath),'acceptance_limits':accept['limits'],'base_audit':record(R/'boot/cosmic-session-source-closure.json'),'base_build_id':base['build_id'],'authentication_checks':checks,'overlay_records':overlays,'overlay_files':file_rows,'combined_userland_runtime_packages':combined_runtime,'combined_notice_only_packages':combined_notice,'new_runtime_packages_over_base':new_runtime,'base_changed_entries':base_changed,'authored_source_files':authored_sources,'hicolor_dataset_provenance':hicolor,'selected_native_packages':selected,'actual_runtime_packages':actual,'notice_only_packages':notice_only,'generator_only_packages':generator_only,'source_files':list(sourcefiles.values()),'source_bytes':sum(f['bytes'] for f in sourcefiles.values()),'missing_source_files':missing,'missing_source_bytes':needed,'own_or_unresolved_files':own,'artwork':dict(record(art),rights_scope='User-provided original artwork; byte integrity verified, no independent rights clearance.'),'controller_sources':controller,'generated_schema_inputs':schema_inputs,'generation_recipes':recipes,'persistent':{'manifest':record(P),'build_id':pm['build_id'],'initramfs_sha256':pm['initramfs_sha256'],'archive_verified':True,'boot_pass_claim':False,'kernel_package':kp,'modules':persistent_modules,'kernel_sources_already_acquired':True,'changed_entries':changed,'authored_storage_recipe':persistent_authored},'budget':{'prior_successful_unique_download_bytes':successful_transfer,'prior_conservative_transfer_bound':conservative_prior,'remaining_conservative_bytes':1024**3-conservative_prior,'original_plan_bytes':190347216,'remaining_source_bytes':needed,'fits_conservative_1GiB_cap':conservative_prior+190347216<=1024**3,'fits_unique_1GiB_cap':successful_transfer+190347216<=1024**3,'downloads_executed':new_acquisition.exists(),'conservative_margin_after_original_plan':1024**3-conservative_prior-190347216,'acquisition_manifest':record(new_acquisition) if new_acquisition.exists() else None,'download_ledger':load(O/'download-ledger.json') if (O/'download-ledger.json').exists() else None},'verification_errors':errors,'warnings':warnings,'gaps':['Current source availability is recorded explicitly; acquired archives remain local, not a delivered source offer.','Generated cache receipts/input/output hashes checked; reproducible output regeneration not performed.','Inherited 0.19 Rust/license/static-runtime/source-delivery gaps remain unchanged.','User artwork byte integrity is not independent rights clearance.','Authored app/controller/wrappers have no separate explicit redistribution LICENSE file located in the inspected project roots; caller must choose/confirm their distribution terms. Native licenses remain independent.','Persistent derivative is inspected only, no boot-pass or durable-state acceptance claim.'],'excluded':['Prospective cosmic-files-portals-stage, not selected in either image','MORK upstream','ECAN upstream']}
assert sha(M)==mh
(O/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
summary={k:report[k] for k in ['schema','scope','avatar_manifest','build_id','initramfs_sha256','focused_acceptance','acceptance_limits','base_audit','base_build_id','actual_runtime_packages','notice_only_packages','generator_only_packages','missing_source_bytes','budget','verification_errors','warnings','gaps','excluded']};summary.update({'inventory':record(O/'inventory.json'),'counting_scope':'Overlay-local counts are separate from combined inherited userland/terminfo counts. Kernel and BusyBox remain separately inherited.','overlay_runtime_package_count':len(actual),'combined_userland_runtime_package_count':len(combined_runtime),'new_runtime_packages_over_base_count':len(new_runtime),'combined_notice_only_package_count':len(combined_notice),'actual_runtime_package_count':len(actual),'notice_only_package_count':len(notice_only),'generator_only_package_count':len(generator_only),'missing_source_file_count':len(missing),'authored_overlay_record_count':len(own),'authored_unique_path_count':len({x['path'] for x in own}),'persistent_build_id':pm['build_id'],'persistent_boot_pass_claim':False})
(R/'boot/avatar-source-closure.json').write_text(json.dumps(summary,indent=2)+'\n')
with (O/'retrieve-missing-sources.sh').open('w') as out:
 out.write('#!/bin/sh\n# PREPARED ONLY. Confirm budget fits before running; no extraction.\nset -eu\nmkdir -p avatar-sources\ncd avatar-sources\n')
 for f in missing:out.write(f"curl --fail --location --output {shlex.quote(f['filename'])} {shlex.quote(f['url'])}\nprintf '%s\\n' {shlex.quote(f['sha256']+'  '+f['filename'])} | sha256sum --check -\n")
print(json.dumps({k:v for k,v in summary.items() if k not in ['actual_runtime_packages','notice_only_packages']},indent=2))
