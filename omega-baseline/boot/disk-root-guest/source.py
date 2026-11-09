"""Streaming root source tar: preserve recorded guest UID/GID without host chown/mount.

Prepared functions only. No build CLI while coordinated capability/space gates remain.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import plan
import transform

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'build/disk-root-guest'

def safe_name(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or str(p)!=name or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Unsafe archive entry name')
    return name

def tar_info(name,mode,size=0,link=None):
    safe_name(name)
    result=tarfile.TarInfo(name);result.uid=0;result.gid=0;result.uname='';result.gname='';result.mtime=0;result.mode=stat.S_IMODE(mode)
    if mode & 0o6000:raise ValueError('Unexpected setid permission')
    if stat.S_ISREG(mode):result.type=tarfile.REGTYPE;result.size=size
    elif stat.S_ISDIR(mode):result.type=tarfile.DIRTYPE
    elif stat.S_ISLNK(mode):
        if link is None or '\0' in link:raise ValueError('Invalid guest symlink')
        result.type=tarfile.SYMTYPE;result.linkname=link
    else:raise ValueError('No host/device/special entries are staged')
    return result

class Slice:
    def __init__(self,stream,size):self.stream=stream;self.remaining=size;self.digest=hashlib.sha256()
    def read(self,n=-1):
        n=self.remaining if n<0 else min(n,self.remaining)
        data=self.stream.read(n)
        if len(data)!=n:raise ValueError('Truncated source payload')
        self.remaining-=len(data);self.digest.update(data);return data
    def verify(self,digest):
        if self.remaining or self.digest.hexdigest()!=digest:raise ValueError('Source file checksum/length mismatch')

def records(stream,expected):
    seen=set()
    while True:
        h=stream.read(110)
        if len(h)!=110 or h[:6]!=b'070701':raise ValueError('Invalid newc source header')
        v=[int(h[6+i*8:14+i*8],16) for i in range(13)]
        if not 1<=v[11]<=4096:raise ValueError('Invalid source name size')
        raw=stream.read(v[11])
        if len(raw)!=v[11] or raw[-1:]!=b'\0':raise ValueError('Invalid source name')
        name=raw[:-1].decode();stream.read(-(110+v[11])%4)
        if name=='TRAILER!!!':break
        safe_name(name)
        if name in seen:raise ValueError('Duplicate source entry')
        seen.add(name);e=expected.get(name,{})
        fields={'mode':v[1],'uid':v[2],'gid':v[3],'bytes':v[6],'rdevmajor':v[9],'rdevminor':v[10]}
        if any(e.get(k)!=value for k,value in fields.items()) or v[2:4]!=[0,0]:raise ValueError('Source metadata mismatch: '+name)
        payload=Slice(stream,v[6]);yield name,e,payload
        payload.verify(e['sha256']);stream.read(-v[6]%4)
    if seen!=set(expected):raise ValueError('Source entry set mismatch')

def source_identity():
    base=json.loads((plan.BASE/'manifest.json').read_text())
    if base['build_id']!=plan.BASE_ID or base['initramfs_sha256']!=plan.BASE_SHA:raise ValueError('Source runtime changed')
    scripts={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['source.py','transform.py','init.sh','data-mount.sh','data-unmount.sh','image.py','data_image.py','bootstrap.py','runner_support.py','plan.py','tooling.py','build.py','verify.py']}
    identity={'source_build_id':plan.BASE_ID,'source_archive_sha256':plan.BASE_SHA,'source_manifest_sha256':hashlib.sha256((plan.BASE/'manifest.json').read_bytes()).hexdigest(),'scripts':scripts,'source_provenance':{k:v for k,v in base.items() if k!='entries'}}
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),identity

def write_source(destination):
    """Future coordinated stream producer; no host tree, chown or full-file buffering."""
    budget=plan.summary()
    if not budget['streaming_space_budget_passed']:raise ValueError('Insufficient free space including 4GiB reserve and future model')
    build_id,identity=source_identity()
    archive=plan.BASE/'files-portals.cpio.gz'
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=plan.BASE_SHA:raise ValueError('Source archive changed')
    expected=json.loads((plan.BASE/'manifest.json').read_text())['entries'];out_records={};pending={};omitted=[]
    output=HashSink(destination)
    with tarfile.open(fileobj=output,mode='w|',format=tarfile.PAX_FORMAT) as tar:
        def emit(name,mode,body=None,size=0,digest=None,link=None):
            if name in out_records:raise ValueError('Duplicate root source output')
            info=tar_info(name,mode,size,link)
            if isinstance(body,bytes):size=len(body);info.size=size;digest=hashlib.sha256(body).hexdigest();body=io.BytesIO(body)
            tar.addfile(info,body)
            out_records[name]={'mode':mode,'uid':0,'gid':0,'bytes':size,'sha256':digest,'link':link}
        with gzip.open(archive,'rb') as stream:
            for name,e,payload in records(stream,expected):
                mode=e['mode'];size=e['bytes']
                if name=='dev/console':payload.read();omitted.append(name);continue
                if name=='init':
                    data=payload.read();pending['usr/libexec/roko-session-init']=(transform.session_init(data),stat.S_IFREG|0o755);omitted.append(name);continue
                if name in ('usr/libexec/roko-storage-mount','usr/libexec/roko-storage-unmount'):
                    payload.read();local='data-mount.sh' if name.endswith('-mount') else 'data-unmount.sh'
                    pending[name]=((HERE/local).read_bytes(),mode);continue
                if name=='usr/libexec/roko-storage-observe.py':
                    data=payload.read()
                    if data.count(b'roko.desktop-storage=')!=1:raise ValueError('Observer phase hook changed')
                    pending[name]=(data.replace(b'roko.desktop-storage=',b'roko.root-data='),mode);continue
                if name.startswith('root/') and stat.S_ISREG(mode):
                    if size>1024**2:raise ValueError('Unexpected large mutable-home seed')
                    data=payload.read();emit(name,mode,data)
                    pending['usr/share/roko/root-seed/'+name.removeprefix('root/')]=(data,mode);continue
                if stat.S_ISLNK(mode):
                    data=payload.read();emit(name,mode,size=size,digest=e['sha256'],link=data.decode())
                elif stat.S_ISDIR(mode):payload.read();emit(name,mode,digest=e['sha256'])
                else:emit(name,mode,payload,size,e['sha256'])
        pending['etc/root-build-id']=((build_id+'\n').encode(),stat.S_IFREG|0o444)
        for name in ['var','root','run','tmp','dev','proc','sys','usr/share/roko/root-seed']:
            if name not in out_records:emit(name,stat.S_IFDIR|0o755,digest=hashlib.sha256(b'').hexdigest())
        for name in list(pending):
            for parent in reversed(PurePosixPath(name).parents):
                key=str(parent)
                if key!='.' and key not in out_records:emit(key,stat.S_IFDIR|0o755,digest=hashlib.sha256(b'').hexdigest())
        for name,(data,mode) in sorted(pending.items()):emit(name,mode,data)
    result={'build_id':build_id,'identity':identity,'entries':out_records,'omitted_original_paths':omitted,'xattrs':'none represented by source newc archive','boot_tested':False,'source_tar_sha256':output.digest.hexdigest(),'source_tar_bytes':output.count}
    return result

class HashSink:
    def __init__(self,destination):self.destination=destination;self.digest=hashlib.sha256();self.count=0
    def write(self,data):
        count=self.destination.write(data)
        if count!=len(data):raise OSError('Short root source stream write')
        self.digest.update(data);self.count+=count;return count
    def flush(self):self.destination.flush()

def stage_source():
    """Optional future diagnostic tar retention; streaming is the preferred disk-budget path."""
    if not plan.summary()['space_budget_passed']:raise ValueError('Retained tar would violate reserved-space budget')
    OUT.mkdir(mode=0o700,exist_ok=True)
    if OUT.is_symlink() or stat.S_IMODE(OUT.stat().st_mode)!=0o700:raise ValueError('Expected private source output')
    with (OUT/'root-source.tar').open('xb') as stream:result=write_source(stream)
    with (OUT/'root-source.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    return result
