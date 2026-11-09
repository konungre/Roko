"""Source-only adapter closure pin. Does not invoke native workers."""
import hashlib
import json
from pathlib import Path
import stat
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CORE=ROOT.parent/'metamo-core-v4'
sys.path.insert(0,str(CORE/'source'))
from gateway import verify_inputs
from proposal_adapter import EXPECTED_MANIFEST

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def freeze():
    target=ROOT/'proof/adapter-inputs.json'
    if target.exists():raise ValueError('Preserve frozen adapter manifest')
    verify_inputs(EXPECTED_MANIFEST)
    files={};entries=sorted(HERE.rglob('*'))
    if any(p.is_symlink() or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo') for p in entries):raise ValueError('No aliases/caches')
    for p in entries:
        if p.is_file():
            if p.stat().st_size>1024**2:raise ValueError('Source cap')
            files[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode)}
    result={'version':1,'scope':'read-only two-case native proposal/checker qualification','files':files,
            'source_tree':str(HERE),'tree_entries':[str(p.relative_to(HERE)) for p in entries],
            'core_manifest':str(CORE/'proof/inputs.json'),'core_manifest_sha256':EXPECTED_MANIFEST,
            'core_native_success_receipt_sha256':'50555393a33955901a9d0c76f93b12a21c7dfcff5d6f4d8c4c4556c28c096d97',
            'native_executed':False}
    target.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'manifest_sha256':sha(target),'source_files':len(files),'bytes':sum(x['bytes'] for x in files.values())}))

if __name__=='__main__':freeze()
