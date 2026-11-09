"""Admit only the fixed private workspace data image, pinning every path component."""
import fcntl
import os
from pathlib import Path
import stat

SIZE = 16 * 1024 * 1024
UUID = '726f6b6f-7072-4f62-8000-000000000006'

def directory(parent, name, private=False, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    s = os.fstat(fd)
    if s.st_uid != os.getuid() or (stat.S_IMODE(s.st_mode) != 0o700 if private else s.st_mode & 0o022):
        os.close(fd)
        raise ValueError('Unsafe owned directory: ' + name)
    return fd

def open_image(root, create=False):
    root = Path(root)
    if not root.is_absolute() or root != root.resolve():
        raise ValueError('Workspace must be absolute and canonical')
    rootfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fds = [rootfd]
    try:
        if os.fstat(rootfd).st_uid != os.getuid() or os.fstat(rootfd).st_mode & 0o022:
            raise ValueError('Unsafe workspace owner/mode')
        build = directory(rootfd, 'build'); fds.append(build)
        private = directory(build, 'disk-root-capability-probe', private=True, create=create); fds.append(private)
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        fd = os.open('data.ext4', flags, 0o600, dir_fd=private)
        try:
            s = os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600:
                raise ValueError('Expected owned private singly-linked regular image')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if create:
                os.ftruncate(fd, SIZE)
                os.fsync(fd); os.fsync(private)
            elif s.st_size != SIZE:
                raise ValueError('Wrong image size')
            return fd
        except BaseException:
            os.close(fd)
            raise
    finally:
        for fd in reversed(fds):
            os.close(fd)
