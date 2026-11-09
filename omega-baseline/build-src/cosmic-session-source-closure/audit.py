"""Session-only source evidence. Read metadata/archives; never install/build/fetch."""
import collections,hashlib,json,pathlib,re,shlex,subprocess,tarfile,tomllib
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent;S=R/'build-src/cosmic-desktop-stage';H=R/'build-src/cosmic-source-closure';M=R/'build/cosmic-session-guest/manifest.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def record(p):return {'path':str(p.relative_to(R)),'sha256':sha(p)}
def pars(text):
 for b in text.split('\n\n'):
  d={};k=None
  for l in b.splitlines():
   if l.startswith((' ','\t')) and k:d[k]+='\n'+l[1:]
   elif ':' in l:k,v=l.split(':',1);d[k]=v.strip()
  if d:yield d
mh=sha(M);m=load(M);dp=load(S/'debian-packages.lock.json');errors=[];warnings=[];checks=[]
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
for p in dp['packages']:
 repo='debian-security' if '/debian-security/' in p['url'] else 'debian';b=bins[repo,p['package'],p['version']];s=srcs[repo,p['source'],p['source_version']];expected={fn:(h,int(z)) for h,z,fn in (x.split() for x in s['Checksums-Sha256'].strip().splitlines())}
 assert b['SHA256']==p['sha256']
 for f in p['corresponding_source_files']:assert expected[f['filename']]==(f['sha256'],f['bytes'])
# Cache is tied to this native package lock; archive bytes are checked before reading ownership.
cache=O/'ownership.json';lock_hash=sha(S/'debian-packages.lock.json')
if cache.exists() and load(cache)['lock']==lock_hash:owners=load(cache)['owners']
else:
 owners={}
 for p in dp['packages']:
  archive=S/'apt/archives'/pathlib.Path(p['filename']).name;assert sha(archive)==p['sha256']
  proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(archive)],stdout=subprocess.PIPE)
  with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
   for f in t:
    if f.isfile() or f.issym() or f.islnk():owners.setdefault(f.name.removeprefix('./'),[]).append(p['package'])
  assert proc.wait()==0
 cache.write_text(json.dumps({'lock':lock_hash,'owners':owners},indent=2)+'\n')
rows=[]
for path,h in m['runtime_sources'].items():
 f=S/'sysroot'/path
 with f.open('rb') as stream:magic=stream.read(4)
 role='notice' if path.startswith('usr/share/doc/') else 'runtime_elf' if magic==b'\x7fELF' else 'runtime_data'
 ok=sha(f)==h
 if not ok:errors.append('Runtime hash mismatch: '+path)
 rows.append({'path':path,'sha256':h,'role':role,'owners':owners.get(path,[]),'verified':ok})
used=sorted({p for r in rows if r['role']!='notice' for p in r['owners']});notice=sorted({p for r in rows if r['role']=='notice' for p in r['owners']}-set(used));unmapped=[r for r in rows if not r['owners']]
selected=[dict(p,copyright=record(S/'sysroot/usr/share/doc'/p['package']/'copyright') if (S/'sysroot/usr/share/doc'/p['package']/'copyright').is_file() else None) for p in dp['packages'] if p['package'] in used]
sourcefiles={f['sha256']:f for p in selected for f in p['corresponding_source_files']}
# Terminfo is a separate stage and must not disappear from the data source inventory.
T=R/'build-src/cosmic-termdata-stage';term=[]
if m.get('terminfo_sources'):
 td=load(T/'debian-packages.lock.json');assert sha(T/'debian-files.lock.json')==m['terminfo_lock_sha256']
 for p in td['packages']:
  repo='debian-security' if '/debian-security/' in p['url'] else 'debian';s=srcs[repo,p['source'],p['source_version']];e={fn:h for h,z,fn in (x.split() for x in s['Checksums-Sha256'].strip().splitlines())}
  for f in p['corresponding_source_files']:assert e[f['filename']]==f['sha256'];sourcefiles[f['sha256']]=f
  archive=T/'apt/archives'/pathlib.Path(p['filename']).name
  assert sha(archive)==p['sha256']
  proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(archive)],stdout=subprocess.PIPE);owned=[]
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
   for member in tar:
    name=member.name.removeprefix('./')
    if member.isfile() and name in m['terminfo_sources']:
     assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==m['terminfo_sources'][name];owned.append(name)
  assert proc.wait()==0
  term.append(dict(p,verified_owned_terminfo_files=owned))
 for path,h in m['terminfo_sources'].items():assert sha(T/'sysroot'/path)==h
# Preserve historical source acquisition, verify reuse rather than trusting paths.
acquired={}
for manifest in H.glob('*source-bundle.manifest.json'):
 for f in load(manifest)['files']:
  p=R/f['local_path'];assert sha(p)==f['sha256'];acquired[f['sha256']]=dict(f,source_manifest=str(manifest.relative_to(R)))
historical_acquired=dict(acquired)
new_sources=O/'acquired-native-sources.json'
if new_sources.exists():
 for f in load(new_sources)['files']:
  assert sha(R/f['local_path'])==f['sha256'];acquired[f['sha256']]=f
missing=[f for h,f in sourcefiles.items() if h not in acquired]
(O/'missing-native-sources.json').write_text(json.dumps(missing,indent=2)+'\n')
# Ten shipped components, not every staged component, define this Rust inventory's scope.
component_names=sorted({a['component'] for a in m['component_assets'] if a.get('binary')});sl={x['component']:x for x in load(S/'sources.lock.json')['components']};dep=load(S/'dependency-sources.lock.json');pkgs={p['manifest_path']:p for p in dep['package_records']};rust={};components=[]
for name in component_names:
 source=sl[name];root=R/source['path'];receipt=load(S/'artifacts'/f'{name}.json');assets=[a for a in m['component_assets'] if a.get('binary') and a['component']==name];artifact_issues=[]
 for a in assets:
  matches=[x for x in receipt['artifacts'] if x['sha256']==a['sha256']]
  if not matches:artifact_issues.append('Guest binary differs from current receipt: '+a['destination'])
  if sha(R/a['source'])!=a['sha256']:artifact_issues.append('Guest binary differs from current local file: '+a['destination'])
 warnings.extend(artifact_issues)
 lock=tomllib.loads((root/'Cargo.lock').read_text());locked={(p['name'],p['version'],p.get('source')):p for p in lock['package']}
 meta=load(S/'logs'/f'{name}-metadata.json')
 for p in meta['packages']:
  path=str(pathlib.Path(p['manifest_path']).relative_to(R));row=pkgs.get(path);key=(p['name'],p['version'],p.get('source'),path)
  if key not in rust:
   evidence=[];parent=pathlib.Path(p['manifest_path']).parent
   for lp in parent.iterdir():
    if lp.is_file() and lp.name.upper().startswith(('LICENSE','COPYING','NOTICE')):evidence.append(record(lp))
   rr={'name':p['name'],'version':p['version'],'source':p.get('source'),'license':p.get('license'),'license_file':p.get('license_file'),'manifest':record(R/path),'license_evidence':evidence,'components':[],'scope':'Resolved metadata superset, not exact binary linkage.'}
   if row:
    rr['manifest_matches_lock']=sha(R/path)==row['manifest_sha256']
    if not rr['manifest_matches_lock']:errors.append('Rust manifest mismatch: '+p['name'])
    if row.get('archive_path'):
     l=locked.get((p['name'],p['version'],p.get('source')));rr['archive']=dict(record(R/row['archive_path']),url=f"https://static.crates.io/crates/{p['name']}/{p['name']}-{p['version']}.crate");rr['archive_matches_cargo_lock']=bool(l and rr['archive']['sha256']==l.get('checksum')==row['archive_sha256'])
     if not rr['archive_matches_cargo_lock']:errors.append('Rust archive mismatch: '+p['name'])
   if not p.get('license') and not p.get('license_file'):rr['license_review_required']=True
   rust[key]=rr
  rust[key]['components'].append(name)
 githead=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();diff=subprocess.check_output(['git','-C',str(root),'diff','--name-only','HEAD'],text=True).splitlines()
 components.append({'component':name,'source':source,'head_matches_source_pin':githead==source['commit'],'tracked_changes':diff,'cargo_lock':record(root/'Cargo.lock'),'lock_matches_receipt':sha(root/'Cargo.lock')==receipt['cargo_lock_sha256'],'receipt':receipt,'receipt_file':record(S/'artifacts'/f'{name}.json'),'guest_binary_issues':artifact_issues,'retrieve_command':f"git clone --no-checkout {shlex.quote(source['url'])} {name} && git -C {name} checkout --detach {source['commit']} && git -C {name} submodule update --init --recursive"})
asset_rows=[]
for a in m['component_assets']:
 if a.get('binary'):continue
 p=R/a['source'];ok=p.is_file() and sha(p)==a['sha256'];row=dict(a,source_verified=ok,role='runtime_translation' if '/i18n/' in a['source'] else 'notice' if '/doc/' in a['destination'] else 'runtime_asset')
 if not ok:errors.append('Asset source mismatch: '+a['source'])
 asset_rows.append(row)
localization=[]
for path,commit in m.get('localization_dependency_commits',{}).items():
 p=R/path;head=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip();localization.append({'path':path,'commit':commit,'verified_head':head==commit,'tracked_changes':subprocess.check_output(['git','-C',str(p),'diff','--name-only','HEAD'],text=True).splitlines(),'license_evidence':[record(f) for f in p.iterdir() if f.is_file() and f.name.upper().startswith(('LICENSE','COPYING'))]})
inherited=load(H/'inherited-guest-source-map.json');inherited_hashes={r['path']:r['sha256'] for p in inherited['packages'] for r in p['verified_guest_files']}
graphics_checks=[{'path':p,'sha256':h,'matches_inherited_verified_payload':inherited_hashes.get(p.removeprefix('boot/tooling/root/'))==h,'role':'host_test_input' if '/qemu/' in p else 'guest_kernel_busybox'} for p,h in m['graphics_sources'].items()]
for x in graphics_checks:
 if x['role']!='host_test_input' and not x['matches_inherited_verified_payload']:errors.append('Inherited graphics source mismatch: '+x['path'])
authored_inputs=[]
for name,h in m['scripts'].items():
 p=R/'boot/cosmic-session-guest'/name;ok=sha(p)==h
 authored_inputs.append(dict(record(p),expected_sha256=h,verified=ok))
 if not ok:errors.append('Authored input mismatch: '+name)
for name,h in m.get('session_client_sources',{}).items():
 p=R/'desktop/session-wayland-test-client'/name;ok=sha(p)==h
 authored_inputs.append(dict(record(p),expected_sha256=h,verified=ok))
 if not ok:errors.append('Session client source mismatch: '+name)
if m.get('session_client_sources'):
 p=R/'desktop/session-wayland-test-client/build/roko-session-wayland-test';assert sha(p)==m['client_sha256']
passed=R/'build/cosmic-session-guest-history/061e179a-passed/manifest.json'
baseline=R/'build/cosmic-session-guest-history/eab3ae7a/manifest.json'
rebind=None
if passed.exists() and load(passed)['build_id']==m['build_id']:
 assert passed.read_bytes()==M.read_bytes()
 v=R/'results/cosmic-session-guest/validation.json';validation=load(v)
 assert validation['build_id']==m['build_id'] and validation['initramfs_sha256']==m['initramfs_sha256'] and validation['passed']
 old=load(baseline);changed_fields=[k for k in m if old.get(k)!=m[k]]
 rebind={'passed_manifest':record(passed),'previous_manifest':record(baseline),'reported_validation':record(v),'validation_passed':True,'validation_scope':'Read and hash-bound existing validation, no new VM run.','unchanged_native_sources':old['runtime_sources']==m['runtime_sources'],'unchanged_component_assets':old['component_assets']==m['component_assets'],'unchanged_terminfo_sources':old['terminfo_sources']==m['terminfo_sources'],'unchanged_localization_commits':old['localization_dependency_commits']==m['localization_dependency_commits'],'unchanged_compositor':old['proven_compositor_sha256']==m['proven_compositor_sha256'],'changed_manifest_fields':changed_fields,'changed_guest_entries':[k for k in m['entries'] if old['entries'].get(k)!=m['entries'][k]],'authored_inputs':authored_inputs,'prior_report_preserved':'build-src/cosmic-session-source-closure/history/'+old['build_id']}
report={'schema':1,'scope':'Reduced COSMIC session provenance and source-availability evidence, not compliance. Standalone 0.18 audit left unchanged.','passed_image_rebind':rebind,'authored_inputs':authored_inputs,'manifest':record(M),'build_id':m['build_id'],'initramfs_sha256':m['initramfs_sha256'],'initramfs_verified':sha(M.parent/'session.cpio.gz')==m['initramfs_sha256'],'native_stage_package_count':len(dp['packages']),'authentication_checks':checks,'runtime_files':rows,'runtime_packages':selected,'notice_only_packages':notice,'unmapped_files':unmapped,'terminfo_packages':term,'terminfo_file_count':len(m.get('terminfo_sources',{})),'native_source_files':list(sourcefiles.values()),'native_source_bytes':sum(f['bytes'] for f in sourcefiles.values()),'missing_native_source_files':missing,'missing_native_source_bytes':sum(f['bytes'] for f in missing),'historical_reused_source_count':sum(h in historical_acquired for h in sourcefiles),'session_acquired_source_count':sum(h in acquired and h not in historical_acquired for h in sourcefiles),'components':components,'rust_packages':list(rust.values()),'runtime_assets':asset_rows,'localization_dependencies':localization,'localization_source_paths_required':m.get('debug_runtime_source_paths_included'),'compiler_and_renderer_evidence':{'pop_launcher_profile_note':'Official Rust 1.93.0 compiler unchanged. Backend here means pop-launcher service, not a compiler codegen backend. Current receipt deliberately disables dev debug assertions; original-dev receipt is retained.','toolchain':record(R/'build-src/cosmic-comp-stage/rust-toolchain.lock.json'),'base_environment':record(R/'build-src/cosmic-comp-stage/env.sh'),'desktop_environment':record(S/'env.sh'),'renderer_features':load(S/'renderer-features.json'),'note':'Current scripts declare Rust 1.93.0 generic x86-64 dev/debug=0. Renderer features are resolved metadata, not proof of exact compiled backend. Per-component profile changes stay in receipts.'},'inherited_graphics_checks':graphics_checks,'kernel_busybox_provenance':str((H/'inherited-guest-source-map.json').relative_to(R)),'warnings':warnings,'verification_errors':errors,'gaps':['No delivered source bundle or legal-compliance conclusion.','Rust metadata is a resolved superset; exact static-linked source and compiler runtime coverage needs review.','Missing package-level Rust license declarations, ancestor licensing, notices and build/install/relink obligations require review.','Debug translation directories retain absolute workspace paths; source-tree placement is part of the current runtime recipe.','Source/body/config/asset licensing and component submodules need preserved source trees; source URLs alone are not delivery.'],'exclusions':['MORK upstream','ECAN upstream']}
assert sha(M)==mh,'Guest changed during audit; rerun.'
(O/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
summary={k:report[k] for k in ['schema','scope','passed_image_rebind','manifest','build_id','initramfs_sha256','initramfs_verified','native_stage_package_count','native_source_bytes','missing_native_source_bytes','historical_reused_source_count','session_acquired_source_count','terminfo_file_count','localization_source_paths_required','warnings','verification_errors','gaps','exclusions']};summary.update({'inventory':record(O/'inventory.json'),'runtime_package_count':len(used),'runtime_packages':used,'notice_only_package_count':len(notice),'notice_only_packages':notice,'missing_native_source_files':len(missing),'built_components':component_names,'rust_resolved_package_records':len(rust),'rust_license_review_records':sum(x.get('license_review_required',False) for x in rust.values()),'runtime_translation_files':sum(x['role']=='runtime_translation' for x in asset_rows),'acquisition_plan':{'file':str((O/'acquisition-plan.json').relative_to(R)),'prior_successful_source_bytes':630439367,'session_acquired_bytes':sum(f['bytes'] for f in load(new_sources)['files']) if new_sources.exists() else 0,'remaining_1GiB_budget_before_session':1024**3-630439367,'successful_source_bytes_combined':630439367+(sum(f['bytes'] for f in load(new_sources)['files']) if new_sources.exists() else 0),'conservative_transfer_upper_bound_with_one_interrupted_pass':630439367+2*119486927,'fits_remaining_download_budget':sum(f['bytes'] for f in missing)<=1024**3-630439367,'executed':new_sources.exists(),'acquired_manifest':record(new_sources) if new_sources.exists() else None}})
(R/'boot/cosmic-session-source-closure.json').write_text(json.dumps(summary,indent=2)+'\n')
with (O/'retrieve-missing-native-sources.sh').open('w') as out:
 out.write('#!/bin/sh\n# Source bytes only. Prepared, not run.\nset -eu\nmkdir -p session-native-sources\ncd session-native-sources\n')
 for f in missing:out.write(f"curl --fail --location --output {shlex.quote(f['filename'])} {shlex.quote(f['url'])}\nprintf '%s\\n' {shlex.quote(f['sha256']+'  '+f['filename'])} | sha256sum --check -\n")
print(json.dumps({k:v for k,v in summary.items() if k not in ['notice_only_packages','runtime_packages']},indent=2))
