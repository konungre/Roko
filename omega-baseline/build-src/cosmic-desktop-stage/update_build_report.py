#!/usr/bin/env python3
"""Summarize existing receipts only; does not build or execute guest software."""
import hashlib,json,pathlib
S=pathlib.Path(__file__).resolve().parent;R=S.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[]
for p in sorted((S/'artifacts').glob('*.json')):
 d=json.loads(p.read_text())
 for a in d['artifacts']:
  f=R/a['path']
  if sha(f)!=a['sha256'] or f.stat().st_size!=a['bytes']:raise RuntimeError('Artifact mismatch: '+str(f))
 artifacts.append({'component':d['component'],'receipt':str(p.relative_to(R)),'receipt_sha256':sha(p),'source_commit':d['source_commit'],'args':d['args'],'artifacts':d['artifacts']})
report={'schema':1,'scope':'Genuine reduced desktop components; build proof only, no full desktop/session runtime claim. Original standalone compositor and guest artifacts remain separate.','epoch_commit':'e98f8289a22f9e612feee7d4c6ba197782db154b','components':artifacts,'single_job':True,'target_cpu':'x86-64 generic','native_package_lock':{'path':str((S/'debian-packages.lock.json').relative_to(R)),'sha256':sha(S/'debian-packages.lock.json')},'dependency_source_lock':{'path':str((S/'dependency-sources.lock.json').relative_to(R)),'sha256':sha(S/'dependency-sources.lock.json')},'original_compositor_sha256':sha(R/'build-src/cosmic-comp-stage/target/debug/cosmic-comp'),'cognitive_image_sha256':sha(R/'build/boot/roko-initramfs.cpio.gz'),'guest_acceptance':'Pending separate session VM validation; see boot/cosmic-session-guest.'}
assert report['original_compositor_sha256']=='c05336d2c59f97b18b0adfa5f6a1c73d3dd52625158a132f8ff61af87bb8255c'
assert report['cognitive_image_sha256']=='8021629f1927dc0e33eea3887dd1a34810e22a5f3cafc2aa2e9e9f54841ff111'
(R/'boot/cosmic-desktop-build.json').write_text(json.dumps(report,indent=2)+'\n')
print('Verified',len(artifacts),'component receipts')
