"""Light planning: metadata/control indexes only; no payload scans, fetch, build or VM."""
import hashlib,json,pathlib,shutil,subprocess,tarfile,re
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent;S=R/'build-src/cosmic-files-portals-stage'
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def record(p):return {'path':str(p.relative_to(R)) if p.is_relative_to(R) else str(p),'sha256':sha(p)}
fmp=R/'build/cosmic-files-portals-guest/manifest.json';fm=load(fmp);rootp=R/'build/disk-root-guest/root-source.json';root=load(rootp);cp=R/'build/roko-corner-guest/bootstrap.json';corner=load(cp);overlayp=S/'overlay-v1.lock.json';overlay=load(overlayp);dp=load(S/'debian-packages.lock.json');native=load(S/'debian-files.lock.json');nf={x['path']:x for x in native['files']}
assert sha(overlayp)==fm['overlay_lock_sha256'];assert sha(S/'debian-files.lock.json')==overlay['native_lock_sha256']
assert root['identity']['source_manifest_sha256']==sha(fmp) and root['identity']['source_build_id']==fm['build_id']
assert corner['build_id']==root['build_id'] and corner['delta']['root_build_id']==root['build_id']
# Reuse exact previously verified archive ownership keyed by package version/hash.
oldlock=load(R/'build-src/cosmic-desktop-stage/debian-packages.lock.json');oldby={p['package']:p for p in oldlock['packages']};oldowners=load(R/'build-src/cosmic-session-source-closure/ownership.json')['owners'];byarchive={}
for path,names in oldowners.items():
 for n in names:byarchive.setdefault(oldby[n]['sha256'],[]).append(path)
byarchive.update(load(R/'build-src/avatar-source-closure/archive-ownership.json'))
cachep=O/'control-ownership.json';controls=load(cachep) if cachep.exists() else {};owners={};control_packages=[]
for p in dp['packages']:
 if p['sha256'] in byarchive:paths=byarchive[p['sha256']];method='prior_verified_archive_cache'
 else:
  if p['sha256'] not in controls:
   archive=S/'apt/archives'/pathlib.Path(p['filename']).name
   proc=subprocess.Popen(['dpkg-deb','--ctrl-tarfile',str(archive)],stdout=subprocess.PIPE);paths=[]
   with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
    for member in t:
     if member.name.removeprefix('./')=='md5sums':paths=[line.split(None,1)[1] for line in t.extractfile(member).read().decode().splitlines() if len(line.split(None,1))==2]
   assert proc.wait()==0;controls[p['sha256']]=paths
  paths=controls[p['sha256']];method='control_index_only_whole_archive_hash_deferred';control_packages.append(p['package'])
 for path in paths:owners.setdefault(path,[]).append({'package':p['package'],'version':p['version'],'method':method})
cachep.write_text(json.dumps(controls,indent=2)+'\n')
rows=[];unmapped=[]
root_hashes={x.get('sha256') for x in root['entries'].values()}
for path,h in overlay['runtime_sources'].items():
 assert nf[path]['sha256']==h
 role='notice' if path.startswith('usr/share/doc/') else 'shipped_native_runtime_or_data'
 # Corresponding overlay byte appears in retained disk-root entry receipt; no root disk scan while VM active.
 retained=h in root_hashes
 row={'path':path,'sha256':h,'role':role,'retained_hash_in_root_manifest':retained,'owners':owners.get(path,[])};rows.append(row)
 if not row['owners']:unmapped.append(row)
actual={p['package'] for r in rows if r['role']!='notice' and r['retained_hash_in_root_manifest'] for p in r['owners']};notice={p['package'] for r in rows if r['role']=='notice' for p in r['owners']}-actual
selected=[p for p in dp['packages'] if p['package'] in actual];sourcefiles={f['sha256']:f for p in selected for f in p['corresponding_source_files']}
# No byte rehash of prior source archives under active VM; preserve acquisition receipt references.
acquired={};receipts=[]
for p in (R/'build-src/cosmic-source-closure').glob('*source-bundle.manifest.json'):
 d=load(p);receipts.append(record(p))
 for f in d['files']:acquired[f['sha256']]=f
for p in [R/'build-src/cosmic-session-source-closure/acquired-native-sources.json',R/'build-src/avatar-source-closure/acquired-sources.json']:
 d=load(p);receipts.append(record(p))
 for f in d['files']:acquired[f['sha256']]=f
missing=[f for h,f in sourcefiles.items() if h not in acquired];sourcepackages=[];misshash={f['sha256'] for f in missing}
for p in selected:
 if any(f['sha256'] in misshash for f in p['corresponding_source_files']):
  key=(p['source'],p['source_version'])
  if key not in {(x['source'],x['version']) for x in sourcepackages}:sourcepackages.append({'source':p['source'],'version':p['source_version'],'files':[f for f in p['corresponding_source_files'] if f['sha256'] in misshash]})
# Rust inventory/receipts: inspect small source metadata only, no binary/registry archive rehash.
dep=load(S/'dependency-sources.lock.json');components=[]
for p in (S/'artifacts').glob('*.json'):
 d=load(p);a=d['artifact'];guest=[path for path,x in root['entries'].items() if x.get('sha256')==a['sha256']];components.append({'receipt':record(p),'component':d['component'],'source_commit':d['source_commit'],'cargo_lock_sha256':d['cargo_lock_sha256'],'binary_hash':a['sha256'],'matching_root_entries':guest,'command':d['command'],'source_license_files':d.get('source_license_files',d.get('license_files',[]))})
review=[{k:p.get(k) for k in ['name','version','source','manifest_path','license','license_file']} for p in dep['package_records'] if not p.get('license') and not p.get('license_file')]
absent=[{'name':p['name'],'version':p['version'],'archive_path':p['archive_path'],'expected_sha256':p['archive_sha256']} for p in dep['package_records'] if p.get('archive_path') and not (R/p['archive_path']).is_file()]
rust_comp=[]
for c in dep['components']:
 lock=R/c['path']/'Cargo.lock';assert sha(lock)==c['cargo_lock_sha256'];rust_comp.append(dict(c,lock=record(lock)))
# Corner is exclusively caller-authored code/config and new artwork bytes; no new native package receipt.
corner_inputs=[]
for x in corner['delta']['records']:
 p=pathlib.Path(x['source']);generated=x['source'].startswith('generated:')
 if not generated:assert p.is_file() and sha(p)==x['sha256']
 corner_inputs.append(dict(x,source_bytes_verified=not generated,classification='generated_caller_test_configuration' if generated else 'caller_authored_artwork' if x['path'].endswith('.png') else 'caller_authored_code_or_configuration'))
# Native caller-authored tracker includes generated third-party protocol bindings.
tracker=R.parent/'roko-corner-prototype/tracker';tracker_record=next(x for x in corner['delta']['records'] if x['path'].endswith('/roko-window-tracker'))
assert sha(tracker/'roko-window-tracker')==tracker_record['sha256']
tracker_files=[record(p) for p in sorted(tracker.iterdir()) if p.is_file() and p.name in ['tracker.c','noop.h','build.sh','LICENSE','SHA256SUMS']]
protocols=[]
for p in sorted((tracker/'protocols').glob('*.xml')):
 text=p.read_text();copyrights=re.findall(r'<copyright>(.*?)</copyright>',text,re.S)
 protocols.append(dict(record(p),embedded_copyright_and_license=[x.strip() for x in copyrights],classification='third_party_protocol_source',upstream_commit_origin='Not separately specified by tracker receipt; exact XML bytes and embedded notices retained.'))
generated_bindings=[record(p) for p in sorted((tracker/'generated').glob('*')) if p.is_file() and p.suffix in ['.c','.h']]
tracker_needed=re.findall(r'\(NEEDED\).*\[([^]]+)\]',subprocess.check_output(['readelf','-d',str(tracker/'roko-window-tracker')],text=True))
tracker_evidence={'elf_needed':tracker_needed,'binary_sha256':tracker_record['sha256'],'staged_matches_local_artifact':True,'source_build_files':tracker_files,'protocols':protocols,'generated_bindings':generated_bindings,'upstream_license_files':[record(p) for p in (tracker/'licenses').glob('*') if p.is_file()],'license_scope':'Tracker MIT LICENSE is separate from embedded third-party protocol notices and from avatar artwork/Python code terms.','generator':'Existing pinned wayland-scanner; no rebuild this pass. Existing inherited wayland source archives already available.'}
for x in corner_inputs:
 if x['path'].endswith('/roko-window-tracker'):x['classification']='caller_authored_native_tracker_with_third_party_protocol_bindings'
missing_source_packages={(p['source'],p['version']) for p in sourcepackages}
license_evidence=[]
for p in selected:
 if (p['source'],p['source_version']) in missing_source_packages:
  cp=S/'sysroot/usr/share/doc'/p['package']/'copyright'
  license_evidence.append({'package':p['package'],'source':p['source'],'source_version':p['source_version'],'copyright':record(cp) if cp.is_file() else None,'debian_license_labels':sorted(set(re.findall(r'^License: (.+)',cp.read_text(errors='replace'),re.M))) if cp.is_file() else [],'note':'Evidence labels only, not a package-wide license conclusion.'})
# Scope is recorded evidence, not a new boot or root-disk integrity proof.
ledger=load(R/'build-src/avatar-source-closure/download-ledger.json');prior=869413221+ledger['received_bytes'];unique=749926294+ledger['received_bytes'];remaining=1024**3-prior;needed=sum(f['bytes'] for f in missing);disk=shutil.disk_usage(R);reserve=4*1024**3;headroom=max(0,disk.free-reserve)
source_storage=sum(f['bytes'] for p in receipts for f in load(R/p['path'])['files'])
report={'schema':1,'scope':'Light read-only metadata/control-index source planning for disk-root Files/portal image and separate corner delta; no heavy verification, download, installation, build or VM.','files_image':record(fmp),'files_build_id':fm['build_id'],'root_source':record(rootp),'root_build_id':root['build_id'],'root_disk_hash_from_prior_validation':load(R/'build/disk-root-guest/validation.json')['root_sha256'],'root_disk_rehashed':False,'corner_bootstrap':record(R/'build/roko-corner-guest/bootstrap.json'),'corner_delta_id':corner['delta_id'],'corner_boot_pass_claim':False,'native_package_lock':record(S/'debian-packages.lock.json'),'signed_metadata_references':dp['metadata'],'fresh_signature_or_payload_reverification':False,'overlay_lock':record(overlayp),'native_files':rows,'runtime_owner_packages':selected,'notice_only_packages':sorted(notice),'unmapped_native_paths':unmapped,'archive_control_only_packages':control_packages,'missing_native_source_files':missing,'missing_native_source_packages':sourcepackages,'prior_acquisition_receipts':receipts,'rust_components':rust_comp,'built_components':components,'rust_resolved_package_count':len(dep['package_records']),'rust_license_review_records':review,'absent_registry_archives':absent,'upstream_assets':overlay['upstream_assets'],'upstream_transforms':overlay['transforms'],'generated_cache_commands':overlay['generated_cache_commands'],'corner_tracker_evidence':tracker_evidence,'new_native_license_evidence':license_evidence,'corner_inputs':corner_inputs,'corner_native_dependency_delta':0,'corner_rights_note':'Caller-authored/selected new code and artwork are distinct from native upstream and third-party protocol XML/bindings in the tracker. Byte identity does not establish redistribution rights; retain authorship/artifact history and choose/confirm licensing.','budget':{'successful_unique_download_bytes':unique,'conservative_download_bound':prior,'remaining_1GiB_bytes':remaining,'missing_native_source_bytes':needed,'download_cap_shortfall_bytes':max(0,needed-remaining),'free_disk_bytes_observed':disk.free,'required_free_reserve_bytes':reserve,'free_headroom_after_reserve':headroom,'compressed_source_addition_bytes':needed,'source_archive_storage_bytes_from_receipts':source_storage,'estimated_source_archive_storage_after_fetch':source_storage+needed,'fits_5GiB_source_archive_limit':source_storage+needed<5*1024**3,'fits_free_headroom_after_reserve':needed<headroom,'unpacked_size_estimated':False,'fetch_authorized_or_executed':False,'deferred_independent_incremental_cap_bytes':25*1024**2,'incremental_cap_margin_after_plan':25*1024**2-needed,'incremental_cap_status':'Parent-directed future sequence only: wait for heavy VM to finish; no fetch now. Keep original 1 GiB accounting unchanged.'},'deferred_verification':['Rehash newly used .deb archives against authenticated index hashes before promoting control-only ownership to verified provenance.','Fresh signatures/index comparisons and selected file/ELF byte checks deferred while VM active.','No multi-GB root hash, root filesystem readback, archive payload extraction or registry archive rehash this pass.','Generated cache commands, source inputs and transformations recorded; no regeneration performed.'],'excluded_optional_lock':'debian-with-vulkan.lock.json adds mesa-vulkan-drivers but is not the selected overlay native lock; not counted unless selected runtime bytes establish use.','licensing_limits':['Inherited source/licensing limitations remain.','Resolved Rust inventory is not exact static-linked dependency closure.','Missing Rust license metadata and upstream/caller asset licenses need review.','Source archive retrieval alone is not complete corresponding-source delivery or legal compliance.']}
(O/'inventory.json').write_text(json.dumps(report,indent=2)+'\n');(O/'missing-native-sources.json').write_text(json.dumps(missing,indent=2)+'\n')
summary={k:report[k] for k in ['schema','scope','files_image','files_build_id','root_source','root_build_id','root_disk_hash_from_prior_validation','root_disk_rehashed','corner_bootstrap','corner_delta_id','corner_boot_pass_claim','budget','deferred_verification','excluded_optional_lock','licensing_limits']};summary.update({'inventory':record(O/'inventory.json'),'runtime_owner_package_count':len(actual),'notice_only_package_count':len(notice),'unmapped_native_path_count':len(unmapped),'missing_native_source_file_count':len(missing),'missing_native_source_package_count':len(sourcepackages),'rust_resolved_package_count':len(dep['package_records']),'rust_license_review_record_count':len(review),'absent_registry_archive_count':len(absent),'corner_input_count':len(corner_inputs),'corner_native_dependency_delta':0,'third_party_tracker_protocol_count':len(protocols)})
(R/'boot/files-corner-source-plan.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
