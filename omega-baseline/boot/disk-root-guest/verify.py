"""Read-only complete ext4 namespace/metadata/content verification via admitted debugfs."""
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import time
import tooling


def parse_listing(text):
    rows=[]
    for line in text.splitlines():
        if not line.strip():continue
        fields=line.split('/')
        if len(fields)!=8 or fields[0] or fields[-1]:raise ValueError('Unexpected debugfs listing record: '+repr(line))
        _,inode,mode,uid,gid,name,size,_=fields
        rows.append({'inode':int(inode),'mode':int(mode,8),'uid':int(uid),'gid':int(gid),'name':name,'bytes':int(size) if size else None})
    return rows

def inode_spec(number):
    if type(number)!=int or number<=0:raise ValueError('Invalid inode number')
    return '<'+str(number)+'>'

def verify_image(fd,manifest,progress=None):
    expected=manifest['entries'];metadata={};hashes={};deadline=time.monotonic()+1200
    with tooling.descriptors('debugfs') as (base,fds,env,receipt):
        def run(command):
            if time.monotonic()>deadline:raise TimeoutError('Root verification deadline')
            p=subprocess.run(base+['-R',command,f'/proc/self/fd/{fd}'],env=env,pass_fds=(*fds,fd),capture_output=True,text=True,timeout=30,check=True)
            if any(line and not line.startswith('debugfs ') for line in p.stderr.splitlines()):raise ValueError('debugfs error: '+p.stderr)
            return p.stdout
        queue=[('',2)];visited=set()
        while queue:
            directory,inode=queue.pop(0)
            if inode in visited:raise ValueError('Directory inode loop')
            visited.add(inode)
            rows=parse_listing(run('ls -p '+inode_spec(inode)))
            for row in rows:
                name=row.pop('name')
                if name in ('.','..'):
                    if directory=='' and name=='.' and (row['uid'],row['gid'],row['mode'])!=(0,0,stat.S_IFDIR|0o755):raise ValueError('Wrong root owner/mode')
                    continue
                if '/' in name or not name:raise ValueError('Unexpected child name')
                path=directory+'/'+name if directory else name
                if path=='lost+found':
                    if (row['mode'],row['uid'],row['gid'])!=(stat.S_IFDIR|0o700,0,0):raise ValueError('Unexpected lost+found metadata')
                    lost=parse_listing(run('ls -p '+inode_spec(row['inode'])))
                    if any(x['name'] not in ('.','..') and x['inode']!=0 for x in lost):raise ValueError('Unexpected lost+found contents')
                    continue
                e=expected.get(path)
                if e is None:raise ValueError('Unexpected filesystem entry: '+path)
                if path in metadata:raise ValueError('Repeated namespace entry')
                if any(row[k]!=e[k] for k in ('mode','uid','gid')):raise ValueError('Wrong ownership/type/mode: '+path)
                if not stat.S_ISDIR(e['mode']) and row['bytes']!=e['bytes']:raise ValueError('Wrong file size: '+path)
                metadata[path]=row
                if stat.S_ISDIR(row['mode']):queue.append((path,row['inode']))
        if set(metadata)!=set(expected):raise ValueError('Missing filesystem entries: '+str(set(expected)-set(metadata)))
        if progress:progress('Verified complete namespace/ownership/modes: '+str(len(metadata))+' entries')
        checked=0
        for path,e in expected.items():
            if stat.S_ISDIR(e['mode']):continue
            inode=metadata[path]['inode']
            if stat.S_ISLNK(e['mode']) and e['bytes']<60:
                text=run('stat '+inode_spec(inode))
                match=re.search(r'^Fast link dest: "(.*)"$',text,re.M)
                if not match or match[1]!=e['link']:raise ValueError('Wrong symlink target: '+path)
                digest=hashlib.sha256(match[1].encode()).hexdigest()
            else:
                p=subprocess.Popen(base+['-R','cat '+inode_spec(inode),f'/proc/self/fd/{fd}'],env=env,pass_fds=(*fds,fd),stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL)
                h=hashlib.sha256();size=0;file_end=min(deadline,time.monotonic()+60)
                try:
                    while True:
                        if time.monotonic()>file_end:raise TimeoutError('File readback bound exceeded: '+path)
                        if not select.select([p.stdout],[],[],.2)[0]:continue
                        chunk=os.read(p.stdout.fileno(),65536)
                        if not chunk:break
                        size+=len(chunk)
                        if size>e['bytes']:raise ValueError('Readback exceeds expected bytes: '+path)
                        h.update(chunk)
                    _,err=p.communicate(timeout=5)
                    if p.returncode or any(x and not x.startswith(b'debugfs ') for x in err.splitlines()):raise ValueError('Readback failed: '+path+' '+err.decode(errors='replace'))
                    if size!=e['bytes']:raise ValueError('Readback length differs: '+path)
                    digest=h.hexdigest()
                finally:
                    if p.poll() is None:p.kill();p.wait(timeout=5)
            if digest!=e['sha256']:raise ValueError('Readback checksum differs: '+path)
            hashes[path]=digest;checked+=1
            if progress and checked%2000==0:progress('Readback checksums verified: '+str(checked))
    return {'passed':True,'verified_entries':len(metadata),'verified_payloads':len(hashes),'metadata':metadata,'payload_sha256':hashes,'tooling':receipt}
