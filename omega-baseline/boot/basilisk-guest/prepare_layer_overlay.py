#!/usr/bin/env python3
"""Stage only verified supplemental GTK-layer-shell/Pycairo files, no VM."""
import importlib.util
import json
from pathlib import Path
import stat
ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'build-src/basilisk-layer-stage'
spec=importlib.util.spec_from_file_location('base',ROOT/'boot/cosmic-guest/build.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def main():
    output=STAGE/'overlay-v1'
    if output.exists():raise SystemExit('Refusing existing overlay')
    lockdata=(STAGE/'debian-files.lock.json').read_bytes()
    c=base.Closure(STAGE/'sysroot',json.loads(lockdata))
    for p in ['usr/lib/x86_64-linux-gnu/libgtk-layer-shell.so.0','usr/lib/x86_64-linux-gnu/girepository-1.0/GtkLayerShell-0.1.typelib','usr/lib/python3/dist-packages/gi/_gi_cairo.cpython-313-x86_64-linux-gnu.so']:
        c.add(p)
    c.tree('usr/lib/python3/dist-packages/cairo')
    c.tree('usr/lib/python3/dist-packages/pycairo-1.27.0.dist-info')
    for name in ['libgtk-layer-shell0','gir1.2-gtklayershell-0.1','python3-cairo','python3-gi-cairo']:
        c.add('usr/share/doc/'+name+'/copyright')
    baselock=ROOT/'build-src/basilisk-stage/overlay.lock.json'
    existing={x['path']:x for x in json.loads(baselock.read_bytes())['files']}
    records=[];shared=[]
    for name,(data,mode) in c.files.items():
        digest=base.sha(data);mode=stat.S_IMODE(mode)
        if name in existing:
            if (digest,mode)!=(existing[name]['sha256'],existing[name]['mode']):raise ValueError('Nonidentical base collision: '+name)
            shared.append(name);continue
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(mode)
        records.append({'path':name,'kind':'file','sha256':digest,'mode':mode})
    result={'schema':1,'files':records,'base_overlay_lock_sha256':base.sha(baselock.read_bytes()),'source_lock_sha256':base.sha(lockdata),'identical_shared_files':shared,'runtime_sources':c.sources,'bytes':sum((output/x['path']).stat().st_size for x in records),'scope':'Supplemental dependency overlay only, apply with verified base overlay; no application changes or display test'}
    (STAGE/'overlay-v1.lock.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'files':len(records),'shared':len(shared),'bytes':result['bytes']}))
if __name__=='__main__':main()
