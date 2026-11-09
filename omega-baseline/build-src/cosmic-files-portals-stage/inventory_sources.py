#!/usr/bin/env python3
import hashlib,json,pathlib,subprocess,tomllib
S=pathlib.Path(__file__).resolve().parent;R=S.parents[1];C=R/'build-src/cosmic-comp-stage/cargo-home';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();components=[];packages={};gits={}
for item in json.loads((S/'sources.lock.json').read_text())['components']:
 n=item['component'];source=R/item['path'];mfile=S/'logs'/f'{n}-metadata.json'
 if not mfile.exists() or not mfile.stat().st_size:continue
 m=json.loads(mfile.read_text());lock=tomllib.loads((source/'Cargo.lock').read_text());checks={(x['name'],x['version']):x['checksum'] for x in lock['package'] if 'checksum' in x};actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert actual==item['commit'];assert subprocess.run(['git','-C',str(source),'diff','--quiet','HEAD']).returncode==0
 components.append({**item,'cargo_lock_sha256':sha(source/'Cargo.lock'),'offline_metadata_packages':len(m['packages'])})
 for p in m['packages']:
  key=(p['name'],p['version'],p.get('source') or p['manifest_path']);manifest=pathlib.Path(p['manifest_path']);entry={'name':p['name'],'version':p['version'],'source':p.get('source'),'manifest_path':str(manifest.relative_to(R)),'manifest_sha256':sha(manifest),'license':p.get('license'),'license_file':p.get('license_file'),'rust_version':p.get('rust_version')}
  if str(p.get('source','')).startswith('registry+'):
   archives=list((C/'registry/cache').glob('*/'+p['name']+'-'+p['version']+'.crate'));assert len(archives)==1;h=sha(archives[0]);assert h==checks[p['name'],p['version']];entry['archive_path']=str(archives[0].relative_to(R));entry['archive_sha256']=h
  if str(p.get('source','')).startswith('git+'):
   parts=manifest.parts;i=parts.index('checkouts');root=pathlib.Path(*parts[:i+3]);expected=p['source'].split('#')[-1]
   if str(root.relative_to(R)) not in gits:
    actual=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();assert actual==expected;status=subprocess.check_output(['git','-C',str(root),'submodule','status','--recursive'],text=True);assert not any(x.startswith(('-', '+', 'U')) for x in status.splitlines());gits[str(root.relative_to(R))]={'commit':actual,'submodules':status.splitlines()}
  packages[key]=entry
result={'schema':1,'components':components,'package_records':list(packages.values()),'git_checkouts':gits,'licensing':'Declared metadata inventoried; source license files retained, no redistribution clearance implied.'};(S/'dependency-sources.lock.json').write_text(json.dumps(result,indent=2)+'\n');print('Verified',len(components),'component locks,',len(packages),'unique target package records,',len(gits),'Git checkout revisions')
