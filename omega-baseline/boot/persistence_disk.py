"""Private workspace image admission, never an arbitrary host device/path."""
import fcntl
import os
from pathlib import Path
import stat

DISK_BYTES = 32 * 1024 * 1024

def open_image(root, *, create=False):
    root = Path(root)
    if root != root.resolve():
        raise ValueError('Workspace path must be canonical')
    directory = root / 'build' / 'guest-state'
    if (root / 'build').is_symlink():
        raise ValueError('Build directory cannot be a symlink')
    if create:
        directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Expected private owned image directory')
    dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(dirfd).st_ino != info.st_ino or os.fstat(dirfd).st_dev != info.st_dev:
            raise ValueError('Image directory changed')
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        fd = os.open('state.raw', flags, 0o600, dir_fd=dirfd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Expected private singly-linked regular image')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if create:
                os.ftruncate(fd, DISK_BYTES)
                os.fsync(fd)
                os.fsync(dirfd)
            elif info.st_size != DISK_BYTES:
                raise ValueError('Incorrect image size')
            return fd
        except BaseException:
            os.close(fd)
            raise
    finally:
        os.close(dirfd)
