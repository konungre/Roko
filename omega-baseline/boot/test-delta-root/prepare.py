"""Static tiny-bootstrap delta contract; returns files only, never assembles or launches."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ROOT_ID='32e03cfba11b02412dddd0a0a14c56b03a1290dcb5fa0e6710524b9f3ef78c80'
ROOT_SHA='8fa91b7751abae9d16b4022402ac22b85cd308fa67810b809d4ad1f5d42ea03d'
HOOK=b'$BB cp -a /newroot/usr/share/roko/root-seed/. /newroot/root/ || fail seed-home\n'
LIMIT=2*1024**2

def sha(data):return hashlib.sha256(data).hexdigest()
def safe_name(name):
    p=PurePosixPath(name)
    if not re.fullmatch(r'[A-Za-z0-9_.+/-]+',name) or p.is_absolute() or '..' in p.parts or str(p)!=name:
        raise ValueError('Unsafe delta path')
    return name

def read_regular(root,relative,mode=None,digest=None):
    safe_name(relative);path=root/relative
    for part in [path,*path.parents]:
        if part==root.parent:break
        if part.is_symlink():raise ValueError('Delta source symlink')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Expected singly-linked regular delta source')
    observed=stat.S_IMODE(info.st_mode)
    if observed not in (0o444,0o644,0o755) or (mode is not None and mode!=observed):raise ValueError('Unexpected delta mode')
    data=path.read_bytes()
    if len(data)>LIMIT or (digest is not None and sha(data)!=digest):raise ValueError('Delta source size/hash mismatch')
    return data,observed

def installer(records,delta_id):
    lines=['#!/bin/sh','set -eu','BB=/bin/busybox','DEST=/newroot/run/roko-test-overlay',
           '[ ! -e "$DEST" ] && [ ! -L "$DEST" ]','$BB mkdir -m 700 "$DEST"',
           '$BB cp -a /roko-test-seed/. "$DEST/"','cd "$DEST"',
           '[ "$($BB stat -c %u:%g:%a .)" = 0:0:700 ]',
           '$BB sha256sum -c /roko-test-sha256']
    directories=set()
    for rec in records:
        path=rec['path'];safe_name(path)
        for p in PurePosixPath(path).parents:
            if str(p)!='.':directories.add(str(p))
    for path in sorted(directories):
        lines.extend([f'[ -d "./{path}" ] && [ ! -L "./{path}" ]',f'[ "$($BB stat -c %u:%g:%a "./{path}")" = 0:0:700 ]'])
    for rec in records:
        path=rec['path'];mode=oct(rec['mode'])[2:]
        lines.extend([f'[ -f "./{path}" ] && [ ! -L "./{path}" ]',f'[ "$($BB stat -c %u:%g:%h:%a "./{path}")" = 0:0:1:{mode} ]'])
    lines.append('echo ROKO_TEST_DELTA_READY '+delta_id)
    return ('\n'.join(lines)+'\n').encode()

def derive_init(original):
    expected=json.loads((ROOT/'build/disk-root-guest/bootstrap.json').read_text())
    if expected['build_id']!=ROOT_ID or sha(original)!=expected['entries']['init']['sha256'] or original.count(HOOK)!=1:
        raise ValueError('Accepted bootstrap init/hook changed')
    return original.replace(HOOK,b'/bin/busybox sh /roko-test-install.sh || fail test-delta\n'+HOOK)

def prepare(which='combined'):
    if which not in ('combined','files','corner'):raise ValueError('Unknown fixed delta selection')
    receipt=json.loads((ROOT/'build/disk-root-guest/validation.json').read_text())
    if not receipt['passed'] or receipt['build_id']!=ROOT_ID or receipt['root_sha256']!=ROOT_SHA:raise ValueError('Accepted root identity changed')
    raw=None
    if which in ('combined','corner'):
        inputs_path=ROOT/'boot/roko-corner-guest/inputs.json';raw=inputs_path.read_bytes();inputs=json.loads(raw)
        stage=ROOT.parent/'roko-corner-stage-v1';observer=ROOT.parent/'roko-corner-observe-v1.py'
        if Path(inputs['stage'])!=stage or Path(inputs['observer'])!=observer:raise ValueError('Unexpected delta source roots')
    values={};records=[]
    def add(dest,data,mode,source):
        safe_name(dest)
        if dest in values:raise ValueError('Duplicate delta output')
        values[dest]=(data,mode)
        records.append({'path':dest,'sha256':sha(data),'mode':mode,'bytes':len(data),'source':source})
    if which in ('combined','corner'):
        for rec in inputs['files']:
            data,mode=read_regular(stage,rec['path'],rec['mode'],rec['sha256'])
            if len(data)!=rec['bytes']:raise ValueError('Corner input byte count changed')
            add('corner/'+rec['path'],data,mode,str(stage/rec['path']))
        data,mode=read_regular(observer.parent,observer.name,digest=inputs['observer_sha256'])
        add('corner/observe.py',data,mode,str(observer))
    if which in ('combined','files'):
        for name in ['diagnose.py','diagnostic-entry.sh','probe.py']:
            data,mode=read_regular(ROOT/'boot/cosmic-files-portals-guest',name)
            add('files/'+name,data,mode,str(ROOT/'boot/cosmic-files-portals-guest'/name))
    environment=b'# Explicit test-terminal helpers only; no autostart.\n'
    if which in ('combined','corner'):
        environment+=b'rc() { /usr/bin/python3.13 /run/roko-test-overlay/corner/observe.py /run/roko-test-overlay/corner/usr/share/roko/corner --overlay --perch-active --roko-root /opt/roko --state-dir /root/.local/state/roko-corner-test >/dev/console 2>&1; }\n'
    if which in ('combined','files'):
        environment+=b'fp() { /bin/sh /run/roko-test-overlay/files/diagnostic-entry.sh "$@"; }\n'
    add('env.sh',environment,0o444,'generated:explicit-test-functions')
    if sum(len(data) for data,mode in values.values())>LIMIT:raise ValueError('Tiny delta payload exceeds two MiB budget')
    records.sort(key=lambda r:r['path'])
    identity={'root_build_id':ROOT_ID,'root_sha256':ROOT_SHA,'selection':which,'corner_inputs_sha256':sha(raw) if raw is not None else None,
              'source_sha256':sha(Path(__file__).read_bytes()),'records':records}
    delta_id=sha(json.dumps(identity,sort_keys=True).encode());entries={}
    for path,(data,mode) in values.items():
        name='roko-test-seed/'+path;entries[name]=(data,stat.S_IFREG|mode,0,0)
        for p in PurePosixPath(name).parents:
            if str(p)!='.':entries.setdefault(str(p),(b'',stat.S_IFDIR|0o700,0,0))
    entries['roko-test-sha256']=((''.join(r['sha256']+'  '+r['path']+'\n' for r in records)).encode(),stat.S_IFREG|0o444,0,0)
    entries['roko-test-install.sh']=(installer(records,delta_id),stat.S_IFREG|0o700,0,0)
    return entries,dict(identity,delta_id=delta_id,payload_bytes=sum(len(x[0]) for x in values.values()),assembly_performed=False)

if __name__=='__main__':
    _,report=prepare();print(json.dumps({k:report[k] for k in ['delta_id','payload_bytes','assembly_performed']},indent=2))
