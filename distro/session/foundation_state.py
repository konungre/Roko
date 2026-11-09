"""Qualification-only XDG state adapter for the preserved non-root COSMIC guest.

Fixed private virtual disk only. Not an installer or production disk discovery.
"""
import ctypes
import json
import os
from pathlib import Path
import stat
import uuid

UUID = "726f6b6f-7374-4361-8000-000000000041"
MOUNT = Path("/run/roko-foundation-state")
STATE = Path("/home/roko/.local/state")
VALUE = {"schema": "roko-foundation-state-v1", "revision": 1, "payload": "cold-boot-checkpoint"}
RAW = (json.dumps(VALUE, sort_keys=True, separators=(",", ":")) + "\n").encode()
NAME = "foundation-checkpoint.json"


def phase():
    tokens = Path("/proc/cmdline").read_text().split()
    phases = [token.split("=", 1)[1] for token in tokens if token.startswith("roko.foundation-state=")]
    if len(phases) != 1 or phases[0] not in ("write", "read"):
        raise ValueError("Explicit unique write/read qualification phase required")
    return phases[0]


def mount(source, target, kind, flags):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    args = [value.encode() if value is not None else None for value in (source, str(target), kind)]
    if libc.mount(*args, flags, None):
        raise OSError(ctypes.get_errno(), "State mount failed")


def private_directory(path, owner):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (owner, owner, 0o700):
        raise ValueError("Private state directory identity mismatch")


def prepare():
    if os.getpid() != 1 or os.getresuid() != (0, 0, 0):
        raise ValueError("Guest PID1 only")
    selected = phase()
    # Host harness exposes only its admitted regular-file image as this block device.
    info = Path("/dev/vda").lstat()
    if not stat.S_ISBLK(info.st_mode):
        raise ValueError("Expected qualification block device")
    fd = os.open("/dev/vda", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if os.pread(fd, 2, 1080) != b"\x53\xef" or os.pread(fd, 16, 1128) != uuid.UUID(UUID).bytes:
            raise ValueError("State filesystem identity mismatch")
    finally:
        os.close(fd)
    MOUNT.mkdir(mode=0o700)
    mount("/dev/vda", MOUNT, "ext4", 2 | 4 | 8)  # nosuid,nodev,noexec
    if selected == "write":
        child = MOUNT / "user-state"
        child.mkdir(mode=0o700)  # never adopt an old state directory on first boot
        os.chown(child, 1000, 1000)
    private_directory(MOUNT / "user-state", 1000)
    private_directory(STATE, 1000)
    mount(str(MOUNT / "user-state"), STATE, None, 4096)
    mount(None, STATE, None, 4096 | 32 | 2 | 4 | 8)
    print("ROKO_FOUNDATION_STATE_MOUNTED " + selected, flush=True)


def user_checkpoint():
    if os.getresuid() != (1000, 1000, 1000) or os.getresgid() != (1000, 1000, 1000):
        raise ValueError("Checkpoint writer must be non-root")
    private_directory(STATE, 1000)
    selected = phase()
    directory = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if selected == "write":
            # Exclusive fixed-size fixture: no existing user file can be overwritten.
            fd = os.open(NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as stream:
                stream.write(RAW)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(directory)
        verify_checkpoint(directory)
    finally:
        os.close(directory)


def verify_checkpoint(directory):
    fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (1000, 1000, 0o600)):
            raise ValueError("Checkpoint file identity mismatch")
        if stream.read(len(RAW) + 1) != RAW:
            raise ValueError("Checkpoint bytes differ")


def root_receipt():
    if os.getpid() != 1 or os.geteuid() != 0:
        raise ValueError("Guest PID1 receipt only")
    fd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        verify_checkpoint(fd)
    finally:
        os.close(fd)
    print("ROKO_FOUNDATION_STATE_VERIFIED " + phase() + " uid=1000 revision=1", flush=True)


def startup_diagnostics():
    """Fixed bounded guest-role logs only; no retry or change to failure outcome."""
    if os.getpid() != 1 or os.geteuid() != 0:
        raise ValueError("Guest PID1 diagnostics only")
    for role in ("dbus", "pipewire", "wireplumber", "session"):
        path = Path("/run/roko-showcase") / (role + ".log")
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
                    raise ValueError("Untrusted role log")
                stream.seek(max(0, info.st_size - 8192))
                tail = stream.read(8192).decode(errors="replace")
            print("ROKO_FOUNDATION_ROLE_LOG " + json.dumps({"role":role,"tail":tail}, separators=(",", ":")), flush=True)
        except Exception:
            print("ROKO_FOUNDATION_ROLE_LOG_UNAVAILABLE " + role, flush=True)
