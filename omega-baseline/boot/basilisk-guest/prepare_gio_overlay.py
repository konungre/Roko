#!/usr/bin/env python3
"""Add exact compiled-path Gio launch helper from verified existing Debian closure."""
import importlib.util,json,stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STAGE=ROOT/'build-src/basilisk-stage'
spec=importlib.util.spec_from_file_location('base',ROOT/'boot/cosmic-guest/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
output=STAGE/'gio-overlay-v1'
if output.exists():raise SystemExit('Refusing existing output')
lockdata=(STAGE/'debian-files.lock.json').read_bytes();c=base.Closure(STAGE/'sysroot',json.loads(lockdata))
c.add('usr/lib/x86_64-linux-gnu/glib-2.0/gio-launch-desktop')
existing={r['path']:r for r in json.loads((STAGE/'overlay-v2.lock.json').read_text())['files']};records=[];shared=[]
for name,(data,mode) in c.files.items():
 mode=stat.S_IMODE(mode);digest=base.sha(data)
 if name in existing:
  assert (digest,mode)==(existing[name]['sha256'],existing[name]['mode']);shared.append(name);continue
 p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(mode)
 records.append({'path':name,'kind':'file','sha256':digest,'mode':mode})
receipt={'schema':1,'files':records,'identical_shared_files':shared,'source_lock_sha256':base.sha(lockdata),'runtime_sources':c.sources,'elfs':c.elfs,'scope':'Exact official Gio launcher helper compiled path; supplement requires existing verified base overlay; no application changes'}
(STAGE/'gio-overlay-v1.lock.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'files':len(records),'shared':len(shared),'paths':[r['path'] for r in records]}))
