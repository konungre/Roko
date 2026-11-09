"""Private regular-file state images; never formats a host block device."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_probe import verify_runtime
from foundation_state import UUID

SIZE = 64 * 1024 * 1024

def open_image(directory, create=False):
    directory = Path(directory)
    info = directory.lstat()
    if directory != directory.resolve() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Private canonical image directory required")
    dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        if create: flags |= os.O_CREAT | os.O_EXCL
        fd = os.open("state.raw", flags, 0o600, dir_fd=dirfd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError("Private singly-linked regular image required")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if create: os.ftruncate(fd, SIZE)
            elif info.st_size != SIZE: raise ValueError("Unexpected image size")
            return fd
        except BaseException:
            os.close(fd); raise
    finally:
        os.close(dirfd)


def create(directory, tooling, upstream_lock):
    directory, tooling = Path(directory), Path(tooling)
    directory.mkdir(mode=0o700)
    raw = Path(upstream_lock).read_bytes()
    records = json.loads(raw)["files"]
    normalized = directory / "formatter-files.lock.json"
    normalized.write_text(json.dumps({"files": {r["path"]: {k:v for k,v in r.items() if k != "path"} for r in records}}))
    verification = verify_runtime(tooling, normalized)
    fd = open_image(directory, create=True)
    try:
        library = tooling / "usr/lib/x86_64-linux-gnu"
        prefix = [str(library / "ld-linux-x86-64.so.2"), "--inhibit-cache", "--library-path", str(library)]
        command = [*prefix, str(tooling / "usr/sbin/mke2fs"), "-t", "ext4", "-F", "-q", "-m", "0",
                   "-U", UUID, "-L", "ROKO_STATE_TEST", "-E", "lazy_itable_init=0,lazy_journal_init=0", f"/proc/self/fd/{fd}"]
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "MKE2FS_CONFIG": str(tooling / "etc/mke2fs.conf")}
        result = subprocess.run(command, pass_fds=(fd,), env=env, capture_output=True, text=True, timeout=60, check=True)
        os.fsync(fd)
        check = subprocess.run([*prefix, str(tooling / "usr/sbin/e2fsck"), "-f", "-n", f"/proc/self/fd/{fd}"],
                               pass_fds=(fd,), env=env, capture_output=True, text=True, timeout=60, check=True)
        report = {"bytes": SIZE, "uuid": UUID, "formatter_inventory": verification,
                  "upstream_lock_sha256": hashlib.sha256(raw).hexdigest(), "format_returncode": result.returncode,
                  "fsck_returncode": check.returncode, "fsck_output": check.stdout + check.stderr}
        (directory / "format.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        os.close(fd)
