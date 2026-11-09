"""Pin reused closure and authored sources. Reads/hashes only; no new native run."""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
from paths import HERE, ROOT, WORKSPACE, SWI, PYTHON, PETTA, SYSTEM, UPSTREAM, MANIFEST

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk:=stream.read(1024**2): h.update(chunk)
    return h.hexdigest()

def freeze():
    if MANIFEST.exists(): raise ValueError('Preserve existing manifest')
    if shutil.disk_usage(ROOT).free < 4*1024**3+8*1024**2: raise ValueError('4GiB reserve after worst writes')
    oldpath=WORKSPACE/'symbolic-ai-v4/proof/inputs.json'
    if sha(oldpath)!='541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0':
        raise ValueError('Prior closure manifest identity')
    old=json.loads(oldpath.read_bytes());files={};aliases={};trees={}
    for root in (SWI,PYTHON,PETTA,SYSTEM):
        expected=old['tree_entries'][str(root)]
        entries=sorted(root.rglob('*'))
        if [str(p.relative_to(root)) for p in entries]!=expected: raise ValueError('Reused closure tree changed')
        trees[str(root)]=expected
        for p in entries:
            if p.is_symlink():
                if old['symlinks'].get(str(p))!=str(p.readlink()): raise ValueError('Reused alias changed')
                aliases[str(p)]=str(p.readlink())
            if p.is_file():
                resolved=p.resolve(strict=True);row=old['files'][str(resolved)]
                if resolved.stat().st_size!=row['bytes'] or stat.S_IMODE(resolved.stat().st_mode)!=row['mode'] or sha(resolved)!=row['sha256']:
                    raise ValueError('Reused closure bytes changed')
                files[str(resolved)]=row
    def add(p):
        if p.resolve()!=p or not p.is_file() or p.stat().st_size>32*1024**2: raise ValueError('Source input domain')
        files[str(p)]={'bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),'sha256':sha(p),'elf':p.read_bytes()[:4]==b'\x7fELF'}
    for root in (HERE,UPSTREAM,ROOT/'review-only'):
        entries=sorted(root.rglob('*'))
        if any(p.is_symlink() or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo') for p in entries): raise ValueError('Authored tree symlink/cache')
        trees[str(root)]=[str(p.relative_to(root)) for p in entries]
        for p in entries:
            if p.is_file(): add(p)
    add(ROOT/'proof/upstream-lock.json')
    host=Path(sys.executable).resolve(strict=True);add(host)
    data={'version':1,'native_executed':False,'scope':'MetaMo MAGUS bounded host subset, not guest or full MetaMo',
          'files':files,'symlinks':aliases,'tree_entries':trees,
          'host_launcher_python':str(host),'host_standard_library_fully_pinned':False,'reused_manifest_sha256':sha(oldpath),'pins':{'PeTTa':'7037f4c2ad378c52fc328004fe216d5118b674f0','MetaMo':'bf97e50a68aa5059457092dfbe70699b7dd1dbe2'},
          'reference_bytes':sum(r['bytes'] for r in files.values())}
    MANIFEST.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'manifest_sha256':sha(MANIFEST),'files':len(files),'reference_bytes':data['reference_bytes']}))

if __name__=='__main__': freeze()
