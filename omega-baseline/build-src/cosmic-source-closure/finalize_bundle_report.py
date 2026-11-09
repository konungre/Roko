import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
reports=[]
for name,inv in [('egl-source-bundle.manifest.json','inventory.json'),('kernel-source-bundle.manifest.json','inherited-guest-source-map.json'),('cosmic-runtime-source-bundle.manifest.json','inventory.json')]:
 p=O/name
 if not p.exists():continue
 d=json.loads(p.read_text());assert d['all_requested_verified'] and not d['errors']
 for f in d['files']:assert sha(R/f['local_path'])==f['sha256'] and (R/f['local_path']).stat().st_size==f['bytes']
 if name=='cosmic-runtime-source-bundle.manifest.json':
  current=next(g for g in json.loads((O/'inventory.json').read_text())['guest_selections'] if g['manifest']==d['guest_manifest'])
  assert {f['sha256'] for f in d['files']} <= {f['sha256'] for f in current['source_archives']}
  d.setdefault('acquisition_guest_manifest_sha256',d['guest_manifest_sha256'])
  d['guest_manifest_sha256']=current['manifest_sha256']
 d['inventory_sha256']=sha(O/inv);d['inventory_path']=str((O/inv).relative_to(R));d['own_probe']='boot/cosmic-guest/egl-probe.c and associated scripts remain in repository; not part of upstream archive set.'
 p.write_text(json.dumps(d,indent=2)+'\n');reports.append({'path':str(p.relative_to(R)),'sha256':sha(p),'files':len(d['files']),'verified_bytes':d['verified_bytes'],'downloaded_bytes':d['downloaded_bytes']})
s=json.loads((R/'boot/cosmic-source-closure.json').read_text());s['acquired_source_sets']=reports;s['downloaded_source_bytes']=sum(x['downloaded_bytes'] for x in reports);s['verified_source_bytes']=sum(x['verified_bytes'] for x in reports);s['inherited_guest_map']={'path':str((O/'inherited-guest-source-map.json').relative_to(R)),'sha256':sha(O/'inherited-guest-source-map.json')}
inventory=json.loads((O/'inventory.json').read_text())
acquired={f['sha256'] for x in reports for f in json.loads((R/x['path']).read_text())['files']}
for guest in inventory['guest_selections']:
 if guest['manifest']=='build/cosmic-guest/manifest.json':
  missing=[f for f in guest['source_archives'] if f['sha256'] not in acquired]
  (O/'cosmic-additional-source-files.json').write_text(json.dumps(missing,indent=2)+'\n')
  s['cosmic_runtime_source_acquisition_gap']={'files':len(missing),'bytes':sum(f['bytes'] for f in missing),'list':str((O/'cosmic-additional-source-files.json').relative_to(R)),'scope':'Additional selected Debian source archive files only; Rust/build/notice obligations remain separate.'}
s['gaps']=sorted(set(x for x in s['gaps'] if not x.startswith(('Debian corresponding-source archives indexed','EGL selected Debian sources','Guest file selection'))) | {'Selected source archive sets are acquired locally, not delivered in source milestones. Final image binding and license/notice obligations require review.'})
assert s['downloaded_source_bytes']<1024**3;assert sum(x.stat().st_size for x in O.rglob('*') if x.is_file())<5*1024**3
(R/'boot/cosmic-source-closure.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({'source_sets':reports,'downloaded_bytes':s['downloaded_source_bytes'],'verified_bytes':s['verified_source_bytes']},indent=2))
