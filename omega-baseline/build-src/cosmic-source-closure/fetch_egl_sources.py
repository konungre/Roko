"""Fetch source bytes only; verify signed-index hashes; never extract/execute."""
import concurrent.futures,hashlib,json,pathlib,shutil,urllib.request,time
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent;D=O/'egl-sources';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inventory=json.loads((O/'inventory.json').read_text());sel=next(x for x in inventory['guest_selections'] if x['manifest']=='build/egl-probe/manifest.json');items=sel['source_archives']
assert sum(x['bytes'] for x in items)<1024**3
old=json.loads((R/'boot/corresponding-sources.lock.json').read_text())['files']
# Include BusyBox already delivered in earlier userland; no additional download.
for name,h in old.items():
 if name.startswith('busybox_'):
  p=R/'boot/tooling/sources'/name
  assert p.is_file() and sha(p)==h
  items.append({'filename':name,'sha256':h,'bytes':p.stat().st_size,'url':None,'earlier_userland_scope':True})
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
report={'schema':1,'scope':'Verified exact official EGL runtime source archive set plus reused earlier BusyBox source set; no full COSMIC closure claim.','inventory_sha256':sha(O/'inventory.json'),'guest_manifest':sel['manifest'],'guest_manifest_sha256':sel['manifest_sha256'],'files':sorted(results,key=lambda x:x['filename']),'errors':errors,'downloaded_bytes':sum(x['bytes'] for x in results if x['acquisition']=='downloaded_official_snapshot'),'verified_bytes':sum(x['bytes'] for x in results),'all_requested_verified':len(results)==len(items) and not errors,'kernel_and_modules':'Excluded from this source set; Debian linux source mapping and retrieval remain separate.','host_qemu':'Guest manifest sources include host QEMU plugin inputs; those are not guest-shipped libraries.','own_probe':'boot/cosmic-guest/egl-probe.c and associated source/build scripts remain in repository; not upstream archive set.','legal_compliance_claim':False}
(O/'egl-source-bundle.manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2));raise SystemExit(bool(errors))
