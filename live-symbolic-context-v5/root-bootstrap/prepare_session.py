#!/usr/bin/env python3
"""Guest PID1 only; source candidate, syscall backend never exercised on host."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import re
import stat
import subprocess
import sys
import time

INSTALL = Path('/usr/lib/roko-unprivileged')
if Path(__file__).absolute()==INSTALL/'prepare_session.py':sys.path.insert(0,str(INSTALL))
import guest_processes as processes
UID = GID = 1000
NATIVE_CONTEXT_RECEIPT = False  # Build-owned; enabling requires separate reviewed source/runtime.
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC = 1, 2, 4, 8
MS_REMOUNT, MS_BIND = 32, 4096
MAX_FILES, MAX_BYTES = 4096, 64 * 1024 * 1024


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def small(path, cap=1048576):
    path = Path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == 0
            and not info.st_mode & 0o022, 'Untrusted input')
    with path.open('rb') as stream:
        data = stream.read(cap + 1)
    require(len(data) <= cap, 'Input bound')
    return data


def directory(path, uid=0, mode=0o755):
    path = Path(path)
    path.mkdir(exist_ok=True)
    require(stat.S_ISDIR(path.lstat().st_mode), 'Not a real directory')
    os.chown(path, uid, uid, follow_symlinks=False)
    os.chmod(path, mode, follow_symlinks=False)


def mount(source, target, kind, flags, data=None):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                          ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    encoded = [v.encode() if v is not None else None for v in (source, target, kind, data)]
    if libc.mount(encoded[0], encoded[1], encoded[2], flags, encoded[3]):
        raise OSError(ctypes.get_errno(), 'Required guest mount failed')


def tmpfs(path, size, mode, uid=0):
    mount('tmpfs', path, 'tmpfs', MS_NODEV | MS_NOSUID | MS_NOEXEC,
          f'size={size},mode={mode:o},uid={uid},gid={uid}')
    directory(path, uid, mode)


MUTABLE_TREES = ('/proc', '/sys', '/dev', '/run', '/home', '/tmp', '/var/tmp',
                 '/var/lib/roko/live-requests')


def mount_rows(text):
    require(type(text) is str and len(text) <= 1048576, 'Mount metadata bound')
    rows = []
    for line in text.splitlines():
        parts = line.split()
        require(len(parts) >= 10 and parts.count('-') == 1, 'Mount metadata malformed')
        split = parts.index('-')
        require(split >= 6 and len(parts) == split + 4, 'Mount metadata fields')
        point = re.sub(r'\\(040|011|012|134)', lambda m: chr(int(m[1], 8)), parts[4])
        require(point.startswith('/'), 'Mountpoint is not absolute')
        rows.append((point, set(parts[5].split(','))))
    return rows


def verify_mounts(text):
    rows = mount_rows(text)
    for target in ('/', '/run/roko-guest-cognition'):
        found = [opts for point, opts in rows if point == target]
        require(len(found) == 1 and 'ro' in found[0] and 'rw' not in found[0],
                'Required readonly mount absent')
        for point, _ in rows:
            if point != target and point.startswith(target.rstrip('/') + '/'):
                allowed = MUTABLE_TREES if target == '/' else ()
                require(any(point == tree or point.startswith(tree + '/') for tree in allowed),
                        'Unexpected mount hides protected input tree')
    # All backing aliases remain root-only: /run and overlay cow parents are 0700/0755 root.


def validate_runtime(root):
    count = 0
    # Do not traverse symlinks or admit hardlink aliases elsewhere on writable /run.
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in ['.'] + dirs + files:
            path = Path(base) if name == '.' else Path(base)/name
            info = path.lstat()
            count += 1
            require(count <= MAX_FILES and info.st_uid == info.st_gid == 0
                    and not info.st_mode & 0o022
                    and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),
                    'Untrusted runtime tree')
            if stat.S_ISREG(info.st_mode):
                require(info.st_nlink == 1, 'Runtime hardlink alias')


def seed_home(home, manifest):
    require(isinstance(manifest, dict) and 0 < len(manifest) <= 16, 'Seed manifest bounds')
    for relative, expected in manifest.items():
        rel = Path(relative)
        require(not rel.is_absolute() and '..' not in rel.parts and relative.startswith('.config/cosmic/'),
                'Only cosmetic seed allowed')
        src = Path('/usr/share/roko/root-seed')
        dst = home
        for piece in rel.parts[:-1]:
            src /= piece
            info = src.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                    'Untrusted seed ancestry')
            dst /= piece
            directory(dst, UID, 0o700)
        data = small(src / rel.name, 65536)
        require(hashlib.sha256(data).hexdigest() == expected, 'Cosmetic seed hash mismatch')
        target = dst / rel.name
        with target.open('xb') as stream:
            stream.write(data)
        os.chown(target, UID, GID)
        os.chmod(target, 0o600)
    wallpaper = home/'.config/cosmic/com.system76.CosmicBackground/v1/all'
    wallpaper.write_bytes(small('/etc/roko-showcase/background.ron', 65536))
    favorites = home/'.config/cosmic/com.system76.CosmicAppList/v1/favorites'
    favorites.write_text('["com.system76.CosmicFiles", "com.system76.CosmicTerm"]\n')


def setup_cgroups():
    target=Path('/sys/fs/cgroup')
    rows=mount_rows(processes.bounded_read(Path('/proc/self/mountinfo'),1048576).decode())
    require(not any(point==str(target) or point.startswith(str(target)+'/') for point,_ in rows),
            'Unexpected existing cgroup mount')
    info=target.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and not info.st_mode&0o022,
            'Kernel cgroup mountpoint unavailable')
    mount('cgroup2',str(target),'cgroup2',MS_NODEV|MS_NOSUID|MS_NOEXEC)
    for name in ('roko-session','roko-session/desktop','roko-session/companion'):
        path=target/name
        path.mkdir(mode=0o755)  # Fresh only, never adopt/delegate an old tree.
        os.chmod(path,0o755,follow_symlinks=False)
    for scope in ('session','desktop','companion'):
        require(processes.cgroup_empty(scope),'Fresh cgroup is populated')
        fd=processes.cgroup_fd(scope,'cgroup.procs',write=True);os.close(fd)
    fd=processes.cgroup_fd('session','cgroup.kill',write=True);os.close(fd)
    require(processes.bounded_read(Path('/proc/self/cgroup'),4096).decode().splitlines()==['0::/'],
            'PID1 must remain outside the owned user subtrees')


def run(argv, timeout=30):
    # No unbounded helper output or exception text goes to console.
    subprocess.run(argv, check=True, timeout=timeout, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                   env={'PATH': '/usr/bin:/bin:/usr/sbin'})


def prepare():
    os.umask(0o077)
    require(os.uname().release == small('/etc/kernel-release', 128).decode().strip(), 'Kernel mismatch')
    for path in ['/home', '/var/lib/roko', '/run/user', '/etc/roko-showcase-xdg']:
        directory(path)
    directory('/root', 0, 0o700)
    for path in ['/dev/pts', '/dev/shm', '/run/udev']:
        directory(path)
    mount('devpts', '/dev/pts', 'devpts', MS_NOSUID | MS_NOEXEC)
    tmpfs('/dev/shm', '128m', 0o1777)
    for path, size, mode, uid in [('/home', '128m', 0o755, 0),
            ('/var/lib/roko/live-requests', '128m', 0o700, UID),
            ('/tmp', '128m', 0o1777, 0), ('/var/tmp', '64m', 0o1777, 0)]:
        tmpfs(path, size, mode, uid)
    for path in ['/home/roko', '/run/user/1000', '/run/user/1000/roko',
                 '/home/roko/.cache', '/home/roko/.config', '/home/roko/.local',
                 '/home/roko/.local/state', '/home/roko/.local/share']:
        directory(path, UID, 0o700)
    seed_home(Path('/home/roko'), json.loads(small(INSTALL/'seed-manifest.json')))
    directory('/run/roko-control', 0, 0o710)
    os.chown('/run/roko-control', 0, GID, follow_symlinks=False)
    directory('/run/roko-showcase', 0, 0o700)
    marker = Path('/run/roko-showcase/live-guest')
    with marker.open('xb') as stream:
        stream.write(b'roko-unprivileged-candidate-v2\n')
    os.chmod(marker, 0o600)
    run(['/usr/lib/systemd/systemd-udevd', '--daemon'])
    modules = small('/etc/roko-showcase/late-module-order', 8192).decode().splitlines()
    require(len(modules) <= 128, 'Module bound')
    for name in modules:
        require(name and all(c.isalnum() or c == '_' for c in name), 'Module name')
        if not Path('/sys/module', name).is_dir():
            try:
                run(['/bin/busybox', 'insmod', '/usr/lib/roko-showcase/modules/'+name+'.ko'])
            except (subprocess.SubprocessError, OSError):
                print('ROKO_LIVE_OPTIONAL_MODULE_FAILED ' + name, flush=True)
    run(['/usr/bin/udevadm', 'trigger', '--action=add'])
    run(['/usr/bin/udevadm', 'settle', '--timeout=20'])
    setup_cgroups()
    validate_runtime('/run/roko-guest-cognition')
    mount('/run/roko-guest-cognition', '/run/roko-guest-cognition', None, MS_BIND)
    mount(None, '/run/roko-guest-cognition', None,
          MS_BIND | MS_REMOUNT | MS_RDONLY | MS_NODEV | MS_NOSUID)
    mount(None, '/', None, MS_REMOUNT | MS_RDONLY | MS_NODEV | MS_NOSUID)
    # proc files report size zero; read with a cap, not ordinary-file metadata checks.
    with open('/proc/self/mountinfo') as stream:
        text = stream.read(1048577)
    require(len(text) <= 1048576, 'Mount metadata bound')
    verify_mounts(text)
    if NATIVE_CONTEXT_RECEIPT is True:
        import context_backing
        require(Path(context_backing.__file__).resolve()==INSTALL/'context_backing.py',
                'Fixed bootstrap identity helper origin required')
        context_backing.capture()
    elif NATIVE_CONTEXT_RECEIPT is not False:
        raise ValueError('Invalid build-owned bootstrap receipt switch')
    # Remain PID1 and keep import/initialization errors inside fail-inert
    # handling. exec would discard this boundary before supervisor imports.
    os.environ.clear()
    os.environ['PATH']='/usr/bin:/bin:/usr/sbin'
    runpy.run_path('/usr/libexec/roko-showcase-supervisor.py',run_name='__main__')
    raise RuntimeError('Supervisor returned')


def main():
    if os.getpid() != 1:raise SystemExit(90)
    try:
        require(Path(__file__).absolute() == INSTALL/'prepare_session.py'
            and os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0), 'Guest preparation identity')
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        prepare()
    except BaseException:
        print('ROKO_UNPRIVILEGED_PREPARE_FAILED recovery=inert', flush=True)
        # Deliberate Power Off IPC is the only shutdown authority. No retry storm.
        while True:
            time.sleep(3600)


if __name__ == '__main__':
    main()
