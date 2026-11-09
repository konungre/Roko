"""Verify the separate official e2fsprogs stage; execute only fixed tooling and image FDs."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'build-src/filesystem-stage'
BASE=STAGE/'sysroot'

def sha(data): return hashlib.sha256(data).hexdigest()

def verify():
    lock=json.loads((STAGE/'debian-files.lock.json').read_text())
    for rec in lock['files']:
        path=BASE/rec['path']
        if rec['kind']=='symlink':
            if not path.is_symlink() or str(path.readlink())!=rec['target']: raise ValueError('Formatter symlink mismatch: '+rec['path'])
        elif path.is_symlink() or not path.is_file() or sha(path.read_bytes())!=rec['sha256'] or stat.S_IMODE(path.stat().st_mode)!=rec['mode']:
            raise ValueError('Formatter runtime mismatch: '+rec['path'])
    packages=json.loads((STAGE/'debian-packages.lock.json').read_text())
    for rec in packages['packages']:
        path=STAGE/'apt/archives'/Path(rec['filename']).name
        if sha(path.read_bytes())!=rec['sha256'] or path.stat().st_size!=rec['bytes']: raise ValueError('Formatter archive mismatch')
    return {'stage_files_lock_sha256':sha((STAGE/'debian-files.lock.json').read_bytes()),
            'stage_packages_lock_sha256':sha((STAGE/'debian-packages.lock.json').read_bytes()),
            'formatter_version':next(p['version'] for p in packages['packages'] if p['package']=='e2fsprogs')}

def execute(tool,image_fd,format_image=False):
    if tool not in ('mke2fs','e2fsck','dumpe2fs') or (format_image != (tool=='mke2fs')): raise ValueError('Unsupported filesystem tool operation')
    provenance=verify()
    paths=[BASE/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2',BASE/'usr/sbin'/tool]
    fds=[]
    try:
        records={r['path']:r for r in json.loads((STAGE/'debian-files.lock.json').read_text())['files']}
        for path in paths:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW); fds.append(fd)
            st=os.fstat(fd); rec=records[str(path.relative_to(BASE))]
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_nlink!=1 or st.st_mode & 0o022 or sha(os.pread(fd,st.st_size,0))!=rec['sha256']:
                raise ValueError('Tool descriptor admission failed')
        from image import UUID
        args={'mke2fs':['-t','ext4','-F','-q','-m','0','-U',UUID,'-L','ROKO_STATE','-E','lazy_itable_init=0,lazy_journal_init=0'],
              'e2fsck':['-f','-n'], 'dumpe2fs':['-h']}[tool]
        cmd=[f'/proc/self/fd/{fds[0]}','--library-path',str(BASE/'usr/lib/x86_64-linux-gnu'),f'/proc/self/fd/{fds[1]}',*args,f'/proc/self/fd/{image_fd}']
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C','MKE2FS_CONFIG':str(BASE/'etc/mke2fs.conf')}
        result=subprocess.run(cmd,env=env,pass_fds=(*fds,image_fd),capture_output=True,text=True,timeout=60,check=True)
        return provenance,result.stdout+result.stderr
    finally:
        for fd in fds: os.close(fd)
