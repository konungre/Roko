"""Read-only audit of pinned source metadata; writes only its own reports."""
import hashlib,json,pathlib,re,shlex,subprocess,tomllib
R=pathlib.Path(__file__).resolve().parents[2]; S=R/'build-src/cosmic-comp-stage'; O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def paragraphs(text):
 for block in text.split('\n\n'):
  d={};k=None
  for l in block.splitlines():
   if l.startswith((' ','\t')) and k:d[k]+='\n'+l[1:]
   elif ':' in l:k,v=l.split(':',1);d[k]=v.lstrip()
  if d:yield d
errors=[]; checks=[]; dp=load(S/'debian-packages.lock.json'); rs=load(S/'rust-sources.lock.json')
sources={}; bins={}
for m in dp['metadata']:
 p=R/m['file']; h=sha(p); release=S/m['verified_release']; section=release.read_text().split('SHA256:\n')[1].split('\nSHA512:')[0]
 kind='Sources' if p.name.endswith('Sources') else 'Packages'; rel='main/source/Sources' if kind=='Sources' else 'main/binary-amd64/Packages'
 expected={x.split()[2]:x.split()[:2] for x in section.splitlines() if len(x.split())==3}
 ok=h==m['sha256']==expected[rel][0] and p.stat().st_size==m['bytes']==int(expected[rel][1]);checks.append({'file':m['file'],'sha256':h,'matches_release_and_lock':ok})
 if not ok:errors.append(m['file'])
 repo='debian-security' if 'debian-security' in p.name else 'debian'
 for d in paragraphs(p.read_text()):
  if kind=='Sources':sources[(repo,d['Package'],d['Version'])]=d
  else:bins[(repo,d['Package'],d['Version'])]=d
packages=[]
for p in dp['packages']:
 repo='debian-security' if '/debian-security/' in p['url'] else 'debian'; d=sources[(repo,p['source'],p['source_version'])]; b=bins[(repo,p['package'],p['version'])]
 expected={n:(h,int(z)) for h,z,n in (l.split() for l in d['Checksums-Sha256'].strip().splitlines())}
 ok=all(expected.get(f['filename'])==(f['sha256'],f['bytes']) for f in p['corresponding_source_files']) and b['SHA256']==p['sha256']
 if not ok:errors.append(p['package'])
 cp=S/'sysroot/usr/share/doc'/p['package']/'copyright'; license_record=None
 if cp.is_file():
  txt=cp.read_text(errors='replace');license_record={'path':str(cp.relative_to(R)),'sha256':sha(cp),'debian_license_labels':sorted(set(re.findall(r'^License: (.+)',txt,re.M))),'note':'Labels are evidence, not a package-wide SPDX conclusion.'}
 row=dict(p);row.update({'signed_index_mapping_verified':ok,'copyright':license_record,'shipped_status':'unknown_until_guest_selection'})
 packages.append(row)
lock=tomllib.loads((S/'source/Cargo.lock').read_text()); bykey={(p['name'],p['version'],p.get('source')):p for p in lock['package']}
rust=[]
for p in rs['packages']:
 row=dict(p); src=p.get('source') or ''; lp=bykey.get((p['name'],p['version'],p.get('source')))
 row['manifest_verified']=sha(S/p['manifest_path'])==p['manifest_sha256']
 row['license_evidence']=[{'path':str((S/x).relative_to(R)),'sha256':sha(S/x)} for x in p['license_files'] if (S/x).is_file()]
 if src.startswith('registry'):
  row['archive_verified']=sha(S/p['archive_path'])==p['archive_sha256']==lp['checksum'];row['retrieve_url']=f"https://static.crates.io/crates/{p['name']}/{p['name']}-{p['version']}.crate"
 elif src.startswith('git+'):
  u,c=src[4:].split('#');u=u.split('?')[0];row['retrieve_command']=f'git clone --no-checkout {shlex.quote(u)} {shlex.quote(p["name"])} && git -C {shlex.quote(p["name"])} checkout --detach {c} && git -C {shlex.quote(p["name"])} submodule update --init --recursive'
 else:row['retrieve_command']='git clone https://github.com/pop-os/cosmic-comp cosmic-comp && git -C cosmic-comp checkout --detach '+rs['commit']+' && git -C cosmic-comp submodule update --init --recursive'
 if not row['manifest_verified'] or row.get('archive_verified') is False:errors.append(p['name'])
 rust.append(row)
report={'schema':1,'scope':'Evidence inventory, not legal compliance or complete corresponding-source delivery. Resolved Rust dependency superset includes non-shipped/build/optional dependencies.','excluded':['MORK upstream sources and binaries','ECAN upstream sources and binaries'],'inputs':{str(p.relative_to(R)):sha(p) for p in [S/'source/Cargo.lock',S/'rust-sources.lock.json',S/'debian-packages.lock.json',S/'build-provenance.json']},'cosmic_source_commit':rs['commit'],'index_checks':checks,'verification_errors':errors,'debian_packages':packages,'rust_packages':rust,'git_checkouts':rs['git_checkouts'],'existing_busybox_glibc_source_lock':load(R/'boot/corresponding-sources.lock.json'),'gaps':['Guest file selection and final image binding pending.','Debian corresponding-source archives indexed, not downloaded by this audit.','Rust package-level license declarations missing for some packages; ancestor evidence needs review.','No claim all notices, installation information, relinking material or required source/build scripts are delivered.','Rust toolchain standard-library/compiler source coverage must be reviewed for statically incorporated runtime code.','Final binary Rust linkage is not determined from Cargo.lock; inventory is a conservative resolved-package superset.']}
(O/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
files={f['url']:f for p in packages for f in p['corresponding_source_files']}
with (O/'retrieve-debian-sources.sh').open('w') as out:
 out.write('#!/bin/sh\n# Review selected scope and download budget first. Not run by audit.\nset -eu\nmkdir -p sources\ncd sources\n')
 for f in files.values():out.write(f"curl --fail --location --output {shlex.quote(f['filename'])} {shlex.quote(f['url'])}\nprintf '%s\\n' {shlex.quote(f['sha256']+'  '+f['filename'])} | sha256sum --check -\n")
summary={'schema':1,'status':'guest_selection_pending','legal_compliance_claim':False,'inventory_path':str((O/'inventory.json').relative_to(R)),'inventory_sha256':sha(O/'inventory.json'),'debian_build_and_runtime_packages':len(packages),'rust_resolved_packages':len(rust),'missing_rust_license_declarations':[p['name'] for p in rust if not p.get('license')],'signed_index_mapping_errors':errors,'all_debian_source_archive_bytes':sum(f['bytes'] for f in files.values()),'source_retrieval_commands':str((O/'retrieve-debian-sources.sh').relative_to(R)),'gaps':report['gaps'],'exclusions':report['excluded']}
(R/'boot/cosmic-source-closure.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
