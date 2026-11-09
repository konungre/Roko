"""Fetch source bytes only; verify signed-index hashes; never extract/execute."""
import concurrent.futures,hashlib,json,pathlib,shutil,urllib.request,time
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent;D=O/'kernel-sources';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inventory=json.loads((O/'inherited-guest-source-map.json').read_text()); items=[f for p in inventory['source_records'] if p['package'].startswith('linux') for f in p['files']]
assert sum(x['bytes'] for x in items)==155065645
sel={'manifest':'build/egl-probe/manifest.json','manifest_sha256':sha(R/'build/egl-probe/manifest.json')}
def fetch(f):
 p=D/f['filename'];r=dict(f);r['local_path']=str(p.relative_to(R))
 if p.exists() and sha(p)==f['sha256']:r['acquisition']='existing_verified'
 else:
  old=R/'boot/tooling/sources'/f['filename']
  if old.is_file() and old.stat().st_size==f['bytes'] and sha(old)==f['sha256']:
   shutil.copyfile(old,p);r['acquisition']='reused_identical_local_source';r['reused_from']=str(old.relative_to(R))
  else:
   assert f['url'] and f['url'].startswith('https://snapshot.debian.org/')
   tmp=p.with_suffix(p.suffix+'.partial');n=0
   with urllib.request.urlopen(f['url'],timeout=90) as src,tmp.open('wb') as dst:
    while b:=src.read(1024*1024):
     n+=len(b)
     if n>f['bytes']:raise ValueError('Response exceeds signed size: '+f['filename'])
     dst.write(b)
   assert n==f['bytes'] and sha(tmp)==f['sha256'],f['filename']
   tmp.replace(p);r['acquisition']='downloaded_official_snapshot'
 assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'];r['verified']=True
 print(f['filename']+' '+r['acquisition'],flush=True);return r
results=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 jobs={pool.submit(fetch,f):f for f in items}
 for job in concurrent.futures.as_completed(jobs):
  try:results.append(job.result())
  except Exception as e:errors.append({'filename':jobs[job]['filename'],'error':str(e)})
report={'schema':1,'scope':'Verified exact official linux-signed-amd64 and underlying linux source archives for inherited EGL guest kernel/modules; no full COSMIC closure claim.','inventory_sha256':sha(O/'inherited-guest-source-map.json'),'guest_manifest':sel['manifest'],'guest_manifest_sha256':sel['manifest_sha256'],'files':sorted(results,key=lambda x:x['filename']),'errors':errors,'downloaded_bytes':sum(x['bytes'] for x in results if x['acquisition']=='downloaded_official_snapshot'),'verified_bytes':sum(x['bytes'] for x in results),'all_requested_verified':len(results)==len(items) and not errors,'kernel_and_modules':'Included in this separate source set; exact pinned versions and checksums in inherited-guest-source-map.json.','host_qemu':'Guest manifest sources include host QEMU plugin inputs; those are not guest-shipped libraries.','own_probe':'boot/cosmic-guest/egl-probe.c and associated source/build scripts remain in repository; not upstream archive set.','legal_compliance_claim':False}
(O/'kernel-source-bundle.manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2));raise SystemExit(bool(errors))
