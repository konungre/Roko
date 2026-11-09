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


def restore(snapshot, directory, expected_sha256, *, checkpoint=lambda phase: None):
    """Restore one pinned snapshot to a NEW private image; never adopt partial work."""
    import re
    if os.geteuid() == 0:
        raise ValueError('Snapshot restoration must be unprivileged')
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Explicit snapshot SHA256 required')
    snapshot, directory = Path(snapshot), Path(directory)
    if directory.parent != directory.parent.resolve():
        raise ValueError('Canonical output parent required')
    source = os.open(snapshot, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(source)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                before.st_nlink != 1 or before.st_size != SIZE or stat.S_IMODE(before.st_mode) != 0o600):
            raise ValueError('Expected private owned snapshot of qualification size')
        fcntl.flock(source, fcntl.LOCK_SH | fcntl.LOCK_NB)
        directory.mkdir(mode=0o700)
        dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            target = os.open('state.partial', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
            with os.fdopen(target, 'wb') as output:
                digest = hashlib.sha256()
                offset = 0
                while offset < SIZE:
                    block = os.pread(source, min(1024 * 1024, SIZE-offset), offset)
                    if not block: raise ValueError('Snapshot truncated during restoration')
                    output.write(block); digest.update(block); offset += len(block)
                after = os.fstat(source)
                identity = lambda s: (s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
                if identity(before) != identity(after) or digest.hexdigest() != expected_sha256:
                    raise ValueError('Snapshot changed or digest mismatch')
                output.flush(); os.fsync(output.fileno())
            checkpoint('copy-durable')
            # Verify bytes read from the new file, not just bytes offered to write.
            with (directory/'state.partial').open('rb') as copy:
                if hashlib.file_digest(copy, 'sha256').hexdigest() != expected_sha256:
                    raise ValueError('Restored snapshot readback mismatch')
            checkpoint('copy-verified')
            os.rename('state.partial', 'state.raw', src_dir_fd=dirfd, dst_dir_fd=dirfd)
            os.fsync(dirfd)
            checkpoint('image-published')
            report = {'schema': 'roko-foundation-restored-state-v1', 'bytes': SIZE,
                      'sha256': expected_sha256, 'source_unchanged': True,
                      'filesystem_checked': False, 'guest_read_tested': False}
            with (directory/'restoration.json').open('x') as receipt:
                json.dump(report, receipt, indent=2); receipt.write('\n')
                receipt.flush(); os.fsync(receipt.fileno())
            os.fsync(dirfd)
            return report
        finally:
            os.close(dirfd)
    finally:
        os.close(source)
