"""Bounded bootstrap observation, never model/action authorization.

Shared immutable source for root bootstrap and the unprivileged endpoint. Root
ownership/readonly ancestry is the authority boundary, not a digital signature.
No writes, mounts, privilege changes, commands or native execution are here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

CONTROL=Path('/run/roko-control')
RECEIPT=CONTROL/'native-context-bootstrap.json'
REQUEST=Path('/var/lib/roko/live-requests')
WORK=REQUEST/'native-work'
COW=Path('/run/roko-live-cow')
RUNTIME=Path('/run/roko-guest-cognition')
INSTALL=Path('/usr/lib/roko-unprivileged')
SOURCES=tuple(INSTALL/name for name in ('prepare_session.py','context_backing.py','backing_identity.py'))
TOTAL=128*1024**2
FLOOR=32*1024**2
CAP=8192
MOUNT_CAP=262144
# Exact existing protected-root exceptions from prepare_session.verify_mounts.
MUTABLE_TREES=('/proc','/sys','/dev','/run','/home','/tmp','/var/tmp',str(REQUEST))


def require(value,reason):
    if not value:raise ValueError(reason)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate bootstrap receipt key');result[key]=value
    return result


def decode(raw):
    require(type(raw) is bytes and 1<=len(raw)<=CAP,'Bootstrap receipt byte cap')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite receipt value')))


def device(info):return str(os.major(info.st_dev))+':'+str(os.minor(info.st_dev))


def metadata(path,owner,mode=None):
    require(path.resolve()==path,'Bootstrap identity path is not literal')
    info=path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==owner
        and not info.st_mode&0o022 and (mode is None or stat.S_IMODE(info.st_mode)==mode),
        'Bootstrap directory ownership/type/mode differs')
    return {'device':device(info),'inode':info.st_ino,'owner':info.st_uid,
        'group':info.st_gid,'mode':stat.S_IMODE(info.st_mode)}


def mount_rows(raw):
    require(type(raw) is bytes and 1<=len(raw)<=MOUNT_CAP,'Mountinfo byte cap')
    rows=[];ids=set()
    for line in raw.decode('utf-8').splitlines():
        fields=line.split();require(fields.count('-')==1,'Mountinfo separator');split=fields.index('-')
        require(split>=6 and len(fields)==split+4,'Mountinfo fields')
        require(fields[0].isdecimal() and fields[1].isdecimal() and re.fullmatch(r'[0-9]+:[0-9]+',fields[2]),'Mountinfo identity')
        number=int(fields[0]);require(0<number<2**63 and number not in ids,'Mount identity duplicate/range');ids.add(number)
        def path(value):return re.sub(r'\\(040|011|012|134)',lambda m:chr(int(m[1],8)),value)
        point=path(fields[4]);require(point.startswith('/'),'Mountpoint not absolute')
        rows.append({'id':number,'parent':int(fields[1]),'device':fields[2],
            'root':path(fields[3]),'point':point,'options':sorted(fields[5].split(',')),
            'type':fields[split+1],'source':fields[split+2],
            'super_options':sorted(fields[split+3].split(',')), 'optional':fields[6:split]})
    require(len(rows)<=4096,'Mount entry cap')
    return rows


def mounts(raw):
    rows=mount_rows(raw);result={}
    for role,path in (('root',Path('/')),('runtime',RUNTIME),('request',REQUEST),('cow',COW)):
        found=[row for row in rows if row['point']==str(path)]
        require(len(found)==1,'Exactly one fixed '+role+' mount required');result[role]=found[0]
    for row in rows:
        point=row['point']
        require(point=='/' or any(point==tree or point.startswith(tree+'/') for tree in MUTABLE_TREES),
            'Unexpected mount hides protected root input tree')
    for role in ('root','runtime'):
        opts=result[role]['options'];require('ro' in opts and 'rw' not in opts,'Protected '+role+' mount must be readonly')
    root=result['root'];require(root['type']=='overlay' and
        'upperdir=/run/roko-live-cow/upper' in root['super_options'] and
        'workdir=/run/roko-live-cow/work' in root['super_options'],'Root overlay backing differs')
    request=result['request'];require(request['type']=='tmpfs' and request['root']=='/' and
        {'rw','nodev','nosuid','noexec'}<=set(request['options']),'Private request tmpfs flags differ')
    cow=result['cow'];require(cow['type']=='tmpfs' and 'rw' in cow['options'],'Private COW must remain tmpfs')
    for base in (REQUEST,RUNTIME):
        require(not any(Path(row['point'])!=base and Path(row['point']).is_relative_to(base) for row in rows),
            'Nested mount hides protected request/runtime tree')
    for backing in (COW/'upper',COW/'work'):
        covers=[row for row in rows if backing.is_relative_to(Path(row['point']))]
        length=max(len(Path(row['point']).parts) for row in covers)
        deepest=[row for row in covers if len(Path(row['point']).parts)==length]
        require(len(deepest)==1 and deepest[0] is cow,'Nested mount hides COW backing')
    return result


def small_proc(path,cap):
    with Path(path).open('rb') as stream:data=stream.read(cap+1)
    require(1<=len(data)<=cap,'Kernel identity byte cap');return data


def public_view():
    boot=small_proc('/proc/sys/kernel/random/boot_id',64).decode().strip()
    namespace=os.readlink('/proc/self/ns/mnt')
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot),'Boot ID format')
    require(re.fullmatch(r'mnt:\[[1-9][0-9]{0,19}\]',namespace),'Mount namespace format')
    view=mounts(small_proc('/proc/self/mountinfo',MOUNT_CAP))
    request=metadata(REQUEST,1000,0o700)
    require(request['device']==view['request']['device'],'Request root device differs from tmpfs mount')
    fs=os.statvfs(REQUEST);total=fs.f_blocks*fs.f_frsize
    require(total==TOTAL,'Expected existing 128MiB private request tmpfs')
    return {'boot_id':boot,'mount_namespace':namespace,'mounts':view,
        'request_root':request,'request_total_bytes':total}


def source_hashes():
    result={}
    for path in SOURCES:
        require(path.resolve()==path,'Bootstrap source path not literal');info=path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid==info.st_gid==0 and info.st_nlink==1
            and not info.st_mode&0o222 and 1<=info.st_size<=65536,'Bootstrap source metadata differs')
        with path.open('rb') as stream:raw=stream.read(65537)
        require(len(raw)==info.st_size,'Bootstrap source read differs')
        result[str(path)]=hashlib.sha256(raw).hexdigest()
    return result


def validate(value,current,expected_sources):
    require(type(value) is dict and set(value)=={'version','purpose','public','backing','sources','authorizes_actions','executed_actions'},'Bootstrap receipt schema')
    require(type(value['version']) is int and value['version']==1 and value['purpose']=='guest-storage-observation-only'
        and value['authorizes_actions'] is False and type(value['executed_actions']) is int and value['executed_actions']==0,'Bootstrap receipt scope')
    require(type(expected_sources) is dict and set(expected_sources)==set(map(str,SOURCES))
        and all(type(x) is str and re.fullmatch('[0-9a-f]{64}',x) for x in expected_sources.values()),'Build-owned source anchors missing')
    require(canonical(value['sources'])==canonical(expected_sources),'Bootstrap source identity differs')
    require(canonical(value['public'])==canonical(current),'Bootstrap boot/namespace/mount/request identity changed')
    require(type(value['backing']) is dict and set(value['backing'])==set(map(str,(COW,COW/'upper',COW/'work'))),'Bootstrap backing schema')
    for path,row in value['backing'].items():
        require(type(row) is dict and set(row)=={'device','inode','owner','group','mode'},'Backing identity fields')
        require(row['device']==current['mounts']['cow']['device'] and type(row['inode']) is int and row['inode']>0
            and type(row['owner']) is int and row['owner']==0 and type(row['group']) is int and row['group']==0
            and type(row['mode']) is int and 0<=row['mode']<=0o777 and not row['mode']&0o022
            and (path!=str(COW) or row['mode']==0o700),'Backing identity ownership/device/mode')
    return value


def control_directory():
    for path in (CONTROL,*CONTROL.parents):
        require(path.resolve()==path,'Control ancestry not literal');info=path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'Control ancestry differs')
        if path==CONTROL:require(info.st_gid==1000 and stat.S_IMODE(info.st_mode)==0o710,'Existing root:1000 control0710 required')
        else:require(info.st_gid==0,'Control parent group differs')


def read_receipt(expected_sources):
    control_directory()
    fd=os.open(RECEIPT,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and before.st_gid==1000 and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)==0o440 and 1<=before.st_size<=CAP,'Bootstrap receipt metadata differs')
        raw=os.read(fd,CAP+1);after=os.fstat(fd);pathinfo=RECEIPT.lstat()
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink')
        require(len(raw)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(pathinfo,k) for k in fields),
            'Bootstrap receipt changed during read')
        require(stat.S_ISREG(pathinfo.st_mode),'Bootstrap receipt path no longer regular')
    finally:os.close(fd)
    current=public_view();value=validate(decode(raw),current,expected_sources)
    return value,hashlib.sha256(raw).hexdigest()
