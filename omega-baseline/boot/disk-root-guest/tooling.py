"""Static approval/pin checks and descriptor-pinned official tar population tools."""
from contextlib import contextmanager
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'build-src/filesystem-stage'
F=ROOT/'build-src/cosmic-files-portals-stage'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
formatter=load('disk_root_existing_formatter',ROOT/'boot/filesystem-guest/formatter.py')

def verify():
    result=formatter.verify()
    raw=(F/'debian-files.lock.json').read_bytes();lock=json.loads(raw)
    c=load('root_archive_dependency_closure',ROOT/'boot/cosmic-guest/build.py').Closure(F/'sysroot',lock)
    c.add('usr/lib/x86_64-linux-gnu/libarchive.so.13')
    binary=(E/'sysroot/usr/sbin/mke2fs').read_bytes()
    man=gzip.decompress((E/'sysroot/usr/share/man/man8/mke2fs.8.gz').read_bytes())
    symbols=[b'libarchive.so.13',b'archive_entry_stat',b'archive_read_open_filename',b'archive_read_next_header']
    if not all(x in binary for x in symbols) or b'from standard input' not in man:
        raise ValueError('Exact mke2fs tar/stdin capability evidence changed')
    return dict(result,libarchive_source_lock_sha256=hashlib.sha256(raw).hexdigest(),libarchive_sources=c.sources,
                libarchive_elf_closure=c.elfs,tar_interface_documented=True,tar_code_present=True,
                actual_stdin_ownership_probe_passed=False)

@contextmanager
def descriptors(tool):
    if tool not in ('mke2fs','debugfs'):raise ValueError('Unapproved root-image tool')
    receipt=verify();base=E/'sysroot'
    records={r['path']:r for r in json.loads((E/'debian-files.lock.json').read_text())['files']}
    fds=[]
    try:
        for rel in ['usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2','usr/sbin/'+tool]:
            fd=os.open(base/rel,os.O_RDONLY|os.O_NOFOLLOW);fds.append(fd);s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1 or s.st_mode&0o022 or hashlib.sha256(os.pread(fd,s.st_size,0)).hexdigest()!=records[rel]['sha256']:
                raise ValueError('Tool descriptor failed admission')
        library=str(base/'usr/lib/x86_64-linux-gnu')+':'+str(F/'sysroot/usr/lib/x86_64-linux-gnu')
        cmd=[f'/proc/self/fd/{fds[0]}','--library-path',library,f'/proc/self/fd/{fds[1]}']
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C','MKE2FS_CONFIG':str(base/'etc/mke2fs.conf')}
        yield cmd,tuple(fds),env,receipt
    finally:
        for fd in fds:os.close(fd)

def format_args(image_fd,kind):
    if kind not in ('root','probe'):raise ValueError('Expected fixed root/probe image kind')
    uuid='726f6b6f-726f-4f74-8000-000000000004' if kind=='root' else '726f6b6f-7072-4f62-8000-000000000006'
    return ['-t','ext4','-F','-q','-b','4096','-m','0','-U',uuid,'-L','ROKO_ROOT' if kind=='root' else 'ROKO_PROBE',
            '-J','size=64' if kind=='root' else 'size=4',
            '-E','root_owner=0:0,root_perms=0755,no_copy_xattrs,lazy_itable_init=0,lazy_journal_init=0,nodiscard',
            '-d','-',f'/proc/self/fd/{image_fd}']
