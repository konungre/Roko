#!/usr/bin/env python3
"""Dedicated live guest PID 1; no inference, network or autonomous request loop."""
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time

RUNTIME = Path('/run/roko-showcase')
LOG_CAP = 1024 * 1024
GUEST_FLOOR_KIB = 512 * 1024
STARTUP_SECONDS = 180


def available_kib(text):
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == 'MemAvailable:' and len(fields) == 3 and fields[2] == 'kB':
            return int(fields[1])
    raise ValueError('Guest MemAvailable missing')


def wayland_socket(directory):
    matches = []
    for path in directory.glob('wayland-*'):
        if path.is_symlink():
            continue
        try:
            if stat.S_ISSOCK(path.stat().st_mode):
                matches.append(path)
        except FileNotFoundError:
            continue
    if len(matches) > 1:
        raise ValueError('Ambiguous Wayland sockets')
    return matches[0] if matches else None


def reap_children(children):
    """Reap adopted descendants as PID 1 without stealing Popen child status."""
    by_pid = {process.pid: process for process in children.values()}
    while True:
        try:
            result = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            return
        if result is None:
            return
        if result.si_pid in by_pid:
            by_pid[result.si_pid].poll()
        else:
            try:
                os.waitpid(result.si_pid, os.WNOHANG)
            except ChildProcessError:
                pass


class BoundedLog:
    def __init__(self, path, cap=LOG_CAP):
        self.path, self.cap = path, cap
        self.stream = path.open('wb', buffering=0)
        self.length = 0

    def write(self, block):
        block = block[-self.cap:]
        if self.length + len(block) > self.cap:
            self.stream.seek(0)
            self.stream.truncate()
            self.length = 0
        self.stream.write(block)
        self.length += len(block)

    def close(self):
        self.stream.close()


def main():
    # The marker alone can never authorize host process termination.
    if os.getpid() != 1 or os.getuid() != 0 or not (RUNTIME / 'live-guest').is_file():
        raise SystemExit(90)
    os.umask(0o077)
    stopped = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopped.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopped.__setitem__(0, True))
    selector = selectors.DefaultSelector()
    children = {}
    logs = []

    def start(name, argv, environment=None):
        log = BoundedLog(RUNTIME / (name + '.log'))
        logs.append(log)
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, env=environment, start_new_session=True)
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, log)
        children[name] = process
        return process

    def drain(timeout=0.2):
        for key, _ in selector.select(timeout):
            block = os.read(key.fileobj.fileno(), 16384)
            if block:
                key.data.write(block)
            else:
                selector.unregister(key.fileobj)
                key.fileobj.close()
        reap_children(children)

    error = None
    try:
        start('dbus', ['/usr/bin/dbus-daemon', '--config-file=/etc/dbus-1/roko-session.conf', '--nofork'])
        start('seatd', ['/usr/sbin/seatd', '-u', 'root', '-g', 'root'])
        deadline = time.monotonic() + 30
        while not (Path('/run/seatd.sock').is_socket() and Path('/run/user/0/bus').is_socket()):
            if stopped[0] or time.monotonic() >= deadline or any(p.poll() is not None for p in children.values()):
                raise RuntimeError('Desktop service startup failed')
            drain()
        start('pipewire', ['/usr/bin/pipewire'])
        start('wireplumber', ['/usr/bin/wireplumber'])
        session = start('session', ['/usr/bin/cosmic-session', 'cosmic-comp', '--no-xwayland'])
        deadline = time.monotonic() + STARTUP_SECONDS
        display = None
        while display is None:
            if stopped[0] or time.monotonic() >= deadline or session.poll() is not None:
                raise RuntimeError('Wayland startup failed')
            display = wayland_socket(Path('/run/user/0'))
            drain()
        # The restored session has no autostart feature. Exactly one launch owner.
        environment = dict(os.environ, WAYLAND_DISPLAY=display.name)
        pet = start('basilisk', ['/usr/bin/roko-companion'], environment)
        print('ROKO_LIVE_DESKTOP_STARTED state=volatile inference=not-started', flush=True)
        next_check = 0
        while not stopped[0]:
            drain()
            if session.poll() is not None:
                break
            if any(children[name].poll() is not None for name in ['dbus', 'seatd']):
                raise RuntimeError('Essential desktop service exited')
            if pet.poll() is not None:
                # Do not silently restart or open a fallback permanent window.
                raise RuntimeError('Basilisk exited; ending the live session')
            now = time.monotonic()
            if now >= next_check:
                if available_kib(Path('/proc/meminfo').read_text()) < GUEST_FLOOR_KIB:
                    raise RuntimeError('Guest memory floor reached')
                next_check = now + 1
    except Exception as exc:
        error = str(exc)
        print('ROKO_LIVE_SESSION_FAILED ' + error, flush=True)
    finally:
        # Guest PID 1 only. This includes detached inference descendants; all
        # state is volatile. No user documents or host processes are involved.
        print('ROKO_LIVE_STOPPING state=volatile', flush=True)
        os.kill(-1, signal.SIGTERM)
        end = time.monotonic() + 10
        while time.monotonic() < end:
            drain(0.1)
            for process in children.values():
                process.poll()
        os.kill(-1, signal.SIGKILL)
        for process in children.values():
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        for log in logs:
            log.close()
        selector.close()
        os.sync()
        print('ROKO_LIVE_POWER_OFF read_only_media=1 persistent_state=0', flush=True)
        # No forced unmount claims: the running overlay root remains mounted
        # until kernel poweroff; every backing storage filesystem is read-only.
        subprocess.run(['/bin/busybox', 'poweroff', '-f'], check=False)
        while True:
            time.sleep(1)


if __name__ == '__main__':
    main()
