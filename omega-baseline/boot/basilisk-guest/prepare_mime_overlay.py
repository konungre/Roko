#!/usr/bin/env python3
"""Generate signed-package MIME data privately, without host installation."""
import importlib.util,json,os,stat,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STAGE=ROOT/'build-src/basilisk-stage'
spec=importlib.util.spec_from_file_location('base',ROOT/'boot/cosmic-guest/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def main():
    output=STAGE/'mime-overlay-v1';toolroot=STAGE/'mime-generator-v1'
    if output.exists() or toolroot.exists():raise SystemExit('Refusing existing versioned output')
    lockdata=(STAGE/'debian-files.lock.json').read_bytes();c=base.Closure(STAGE/'sysroot',json.loads(lockdata))
    c.add('usr/bin/update-mime-database')
    c.add('usr/share/mime/packages/freedesktop.org.xml')
    c.add('usr/share/doc/shared-mime-info/copyright')
    for name,(data,mode) in c.files.items():
        dest=output if name.startswith('usr/share/') else toolroot
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(stat.S_IMODE(mode))
    env=dict(os.environ,XDG_DATA_HOME=str(output/'usr/share'),XDG_DATA_DIRS=str(output/'usr/share'))
    subprocess.run([str(toolroot/'lib64/ld-linux-x86-64.so.2'),'--library-path',str(toolroot/'usr/lib/x86_64-linux-gnu'),str(toolroot/'usr/bin/update-mime-database'),str(output/'usr/share/mime')],env=env,check=True)
    records=[]
    for p in sorted(output.rglob('*')):
        if p.is_file():records.append({'path':str(p.relative_to(output)),'kind':'file','sha256':base.sha(p.read_bytes()),'mode':stat.S_IMODE(p.stat().st_mode)})
    receipt={'schema':1,'files':records,'source_lock_sha256':base.sha(lockdata),'generator_verified_sources':c.sources,'scope':'Generated shared-mime-info cache/data from signed Debian 2.4-5+b2 XML; no app/artwork or existing overlay changes','bytes':sum((output/r['path']).stat().st_size for r in records)}
    (STAGE/'mime-overlay-v1.lock.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'files':len(records),'bytes':receipt['bytes']}))
if __name__=='__main__':main()
