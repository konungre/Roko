"""Read-only input freeze. Does not execute PeTTa, SWI, Janus or NARS."""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
from paths import HERE,ROOT,WORKSPACE,SWI,PYTHON,PETTA,SYSTEM,UPSTREAM,MANIFEST

BASE_MANIFEST=WORKSPACE/'symbolic-ai-v4/proof/inputs.json'
BASE_SHA='541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024**2):h.update(b)
    return h.hexdigest()

def freeze():
    if MANIFEST.exists():raise ValueError('Existing frozen manifest is immutable')
    if shutil.disk_usage(ROOT).free<4*1024**3+1024**2:raise ValueError('4GiB disk reserve')
    if sha(BASE_MANIFEST)!=BASE_SHA:raise ValueError('Original host closure identity')
    old=json.loads(BASE_MANIFEST.read_bytes())
    if old['pins']['vendor/PeTTa-omega-release']!='7037f4c2ad378c52fc328004fe216d5118b674f0':raise ValueError('PeTTa pin')
    selected=(SWI,PYTHON,PETTA,SYSTEM)
    files={};trees={};links={}
    for root in selected:
        entries=sorted(root.rglob('*'))
        relative=[str(p.relative_to(root)) for p in entries]
        if old['tree_entries'][str(root)]!=relative:raise ValueError('Original runtime tree membership changed')
        trees[str(root)]=relative
        for p in entries:
            if '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):raise ValueError('Bytecode caches forbidden')
            if p.is_symlink():
                if old['symlinks'].get(str(p))!=str(p.readlink()):raise ValueError('Original alias changed')
                links[str(p)]=str(p.readlink())
            if not p.is_file():continue
            p=p.resolve(strict=True);row=old['files'].get(str(p))
            if not row or p.stat().st_size!=row['bytes'] or stat.S_IMODE(p.stat().st_mode)!=row['mode'] or sha(p)!=row['sha256']:raise ValueError('Original runtime/source bytes changed')
            files[str(p)]=row
    def add(p):
        if p.resolve()!=p or not p.is_file():raise ValueError('New input must be a regular resolved file')
        b=p.read_bytes()
        if len(b)>128*1024**2:raise ValueError('Referenced input cap')
        files[str(p)]={'bytes':len(b),'mode':stat.S_IMODE(p.stat().st_mode),'sha256':hashlib.sha256(b).hexdigest(),'elf':b.startswith(b'\x7fELF')}
    for root in (HERE,UPSTREAM):
        entries=sorted(root.rglob('*'));trees[str(root)]=[str(p.relative_to(root)) for p in entries]
        for p in entries:
            if '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):raise ValueError('Bytecode forbidden')
            if p.is_file():add(p)
    upstream=json.loads((ROOT/'upstream-lock.json').read_bytes())
    for row in upstream['files']:
        if sha(ROOT/row['local_path'])!=row['sha256']:raise ValueError('NARS source pin changed')
    for p in (ROOT/'upstream-lock.json',BASE_MANIFEST):add(p)
    host=Path(sys.executable).resolve(strict=True);add(host)
    result={'version':1,'scope':'NAL-1 subset only, current host; no Omega or ECAN imports',
      'native_executed':False,'pins':{'PeTTa':'7037f4c2ad378c52fc328004fe216d5118b674f0','metta-nars':upstream['commit']},
      'reference_manifest_sha256':BASE_SHA,'host_launcher_python':str(host),'host_standard_library_fully_pinned':False,
      'files':files,'tree_entries':trees,'symlinks':links,'reference_bytes':sum(r['bytes'] for r in files.values())}
    MANIFEST.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'manifest_sha256':sha(MANIFEST),'files':len(files),'reference_bytes':result['reference_bytes'],'native_executed':False}))

if __name__=='__main__':freeze()
