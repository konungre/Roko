#!/usr/bin/env python3
"""Small host-only source derivative; reuse pinned binaries, never copy weights."""
import hashlib,json,shlex
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=ROOT/'build-src/granite-model-guest-stage/candidate-v2'
OUT=ROOT/'build-src/granite-host-companion-stage/candidate-v2/roko'
PYROOT=ROOT/'build-src/basilisk-stage/sysroot'
CLOSURE=ROOT/'build/granite-portable-runtime-v1/relocated-v2'

def sha(data):return hashlib.sha256(data).hexdigest()

def stage():
    old=json.loads((BASE/'manifest.json').read_text());files={};modes={};external={}
    for name,pin in old['files'].items():
        if name.startswith('runtime/granite/') and name not in ('runtime/granite/supervise.py','runtime/granite/memory_guard.py'):
            continue
        data=(BASE/'roko'/name).read_bytes()
        if sha(data)!=pin['sha256']:raise ValueError('Portable candidate source changed')
        files[name]=data;modes[name]=0o444
    for name in ('granite-portable-runtime.lock.json','granite-raw-transport.lock.json'):
        files.pop(name,None);modes.pop(name,None)
    selector=files['adapters/runtime_select.py'].decode()
    before="[sys.executable, str(root / 'runtime/granite/supervise.py')"
    after="[str(root / 'runtime/python313'), str(root / 'runtime/granite/supervise.py')"
    if selector.count(before)!=1:raise ValueError('Python launch anchor changed')
    selector=selector.replace(before,after).replace("'--seconds', '300'","'--seconds', '60'")
    files['adapters/runtime_select.py']=selector.encode()
    provider=files['adapters/granite_guest.py'].decode()
    provider=provider.replace('>= 310:', '>= 70:').replace('exceeded 310 seconds','exceeded 70 seconds').replace('310 - (time.monotonic()', '70 - (time.monotonic()')
    files['adapters/granite_guest.py']=provider.encode()
    guard=files['runtime/granite/memory_guard.py'].decode().replace('AVAILABLE_FLOOR = 512 * 1024**2','AVAILABLE_FLOOR = 2 * 1024**3')
    files['runtime/granite/memory_guard.py']=guard.encode()
    host=(ROOT/'boot/granite-model-guest/host_model.py').read_text().replace('ROOT = Path(__file__).resolve().parents[2]',f'ROOT = Path({str(ROOT)!r})')
    host=host.replace('def open_model():','def open_model(seconds=30):').replace('return fd, verify(fd)','return fd, verify(fd, seconds=seconds)')
    files['adapters/host_model.py']=host.encode();modes['adapters/host_model.py']=0o444
    files['adapters/host_companion.py']=(HERE/'host_companion.py').read_bytes();modes['adapters/host_companion.py']=0o444
    cli=files['scripts/roko.py'].decode().replace('from granite_guest import GraniteGuestProvider as GranitePipeProvider,ALLOWED','from host_companion import HostCompanionProvider as GranitePipeProvider\n from granite_guest import ALLOWED')
    files['scripts/roko.py']=cli.encode()
    model=json.loads((ROOT/'granite-model.lock.json').read_text());model['path']=str(ROOT/model['path'])
    files['granite-model.lock.json']=(json.dumps(model,indent=2)+'\n').encode()
    python=PYROOT/'usr/bin/python3.13';loader=PYROOT/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2';libraries=PYROOT/'usr/lib/x86_64-linux-gnu'
    command=[str(loader),'--inhibit-cache','--glibc-hwcaps-mask','','--library-path',str(libraries),str(python),'-S','-B']
    wrapper='#!/bin/sh\nset -eu\nunset PYTHONPATH PYTHONSTARTUP LD_PRELOAD LD_LIBRARY_PATH\nexport PYTHONHOME='+shlex.quote(str(PYROOT/'usr'))+'\nexport PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONCOERCECLOCALE=0 PYTHONUTF8=1 LC_ALL=C\nexec '+shlex.join(command)+' "$@"\n'
    files['runtime/python313']=wrapper.encode();modes['runtime/python313']=0o555
    relocation=json.loads((ROOT/'results/granite-portable-preparation/relocation-admission.json').read_text())
    for name,pin in relocation['files'].items():
        path=ROOT/'build/granite-portable-runtime-v1'/name
        if sha(path.read_bytes())!=pin['sha256']:raise ValueError('Native closure changed')
        external[str(path)]=pin['sha256']
    # Pin all existing Python standard-library sources/extensions plus its observed
    # exact ELF closure. Nothing here is a model file or a new installation.
    for path in (PYROOT/'usr/lib/python3.13').rglob('*'):
        if path.is_file() and not path.is_symlink() and path.suffix in ('.py','.so'):
            external[str(path)]=sha(path.read_bytes())
    maps=json.loads((ROOT/'results/granite-model-guest-preparation/host-python313-maps.json').read_text())
    for name in maps['mapped_files']:
        path=Path(name)
        if str(path).startswith(str(PYROOT)+'/'):
            external[str(path)]=sha(path.read_bytes())
    for name in json.loads((ROOT/'results/granite-host-companion-preparation/actual-python-maps.json').read_text()):
        path=Path(name)
        if not str(path).startswith(str(PYROOT)+'/'):raise ValueError('Unexpected Python mapping outside exact sysroot')
        external[str(path)]=sha(path.read_bytes())
    external[str(python)]=sha(python.read_bytes());external[str(loader)]=sha(loader.read_bytes())
    bridge=ROOT.parent/'roko-corner-stage-v1/usr/share/roko/corner/task_bridge.py'
    if sha(bridge.read_bytes())!='282c922de9615bb5126de029cb36ba7a49ff100c392cba8fffcc3a06915a0b3d':raise ValueError('Actual avatar bridge changed')
    files['avatar/task_bridge.py']=bridge.read_bytes();modes['avatar/task_bridge.py']=0o444
    manifest={'status':'host-companion-source-only-awaiting-execution-grant','native_closure':str(CLOSURE),
              'optimized_loader_admitted':False,'files':{n:sha(d) for n,d in files.items()},'external_files':external,
              'python_executable':str(python),'python_version':'3.13.5','admission_scope':'native host only, no guest service/export/IPC transport'}
    files['host-companion.lock.json']=(json.dumps(manifest,indent=2)+'\n').encode();modes['host-companion.lock.json']=0o444
    OUT.mkdir(parents=True,exist_ok=False)
    for name,data in files.items():
        path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(modes[name])
    report={'status':'source-prepared-no-model-run','root':str(OUT),'bytes':sum(map(len,files.values())),
            'source_files':{n:{'sha256':sha(d),'bytes':len(d),'mode':modes[n]} for n,d in files.items()},
            'external_pinned_files':len(external),'external_bytes':sum(Path(n).stat().st_size for n in external),
            'native_binaries_reused_unchanged':True,'weights_copied':False,'base_manifest_sha256':sha((BASE/'manifest.json').read_bytes()),
            'model_runs_performed':0,'actual_avatar_bridge_sha256':sha(bridge.read_bytes())}
    (OUT.parent/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'results/granite-host-companion-preparation/stage.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    r=stage();print(json.dumps({k:v for k,v in r.items() if k!='source_files'},indent=2))
