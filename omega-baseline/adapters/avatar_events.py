"""Optional, one-way cosmetic events. These never grant task/action permission.

The v1 publisher/validator protocol is shared with roko-basilisk/avatar_state.py
(2026-11-07 snapshot). Keep its exact three-field wire format compatible. This
adapter has no dependency on the companion, a display server, or its assets.
"""
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import threading
import time

STATES = frozenset({'idle', 'thinking', 'waiting', 'review', 'failed', 'complete'})
TTL = 15
HEARTBEAT_SECONDS = 5


def validate_event(event, now=None):
    now = time.time() if now is None else now
    if not isinstance(event, dict) or set(event) != {'version', 'state', 'time'}:
        raise ValueError('Expected version, state and time only')
    if type(event['version']) is not int or event['version'] != 1 or not isinstance(event['state'], str) or event['state'] not in STATES:
        raise ValueError('Invalid event version or state')
    stamp = event['time']
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp > now + 2 or now - stamp > TTL:
        raise ValueError('Invalid or stale event timestamp')
    return event['state']


def publish_event(path, state, now=None):
    """Atomic last-value publication in an existing owned private directory."""
    now = time.time() if now is None else now
    event = {'version': 1, 'state': state, 'time': now}
    validate_event(event, now)
    path = Path(path)
    parent = path.parent
    info = parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Event parent must be an owned private directory (0700)')
    fd, temp = tempfile.mkstemp(prefix='.avatar-', dir=parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(event, out, allow_nan=False)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class AvatarEvents:
    """Best-effort output, with a heartbeat only inside a real active command.

    Never creates directories, changes permissions, reads commands from the
    event file, or publishes user data. An output failure disables this instance.
    No heartbeat runs at an idle console prompt or after command completion.
    """
    def __init__(self, path, state_dir):
        self.path = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._finished = False
        self._thread = None
        if path is not None:
            try:
                candidate = Path(path).absolute()
                # Cosmetic output must not overwrite a task checkpoint or lock.
                if not candidate.resolve().is_relative_to(Path(state_dir).resolve()):
                    self.path = candidate
            except (OSError, ValueError, RuntimeError):
                pass

    def _publish(self, state):
        if self.path is None:
            return
        try:
            publish_event(self.path, state)
        except Exception:
            self.path = None
            self._stop.set()

    def emit(self, state):
        with self._lock:
            if not self._finished:
                self._publish(state)

    def start(self, state, heartbeat=False):
        self.emit(state)
        if heartbeat and self.path is not None:
            self._thread = threading.Thread(target=self._heartbeat, args=(state,), daemon=True, name='roko-avatar-events')
            try:
                self._thread.start()
            except Exception:
                self._stop.set()

    def _heartbeat(self, state):
        while not self._stop.wait(HEARTBEAT_SECONDS):
            self.emit(state)

    def finish(self, state):
        self._stop.set()
        with self._lock:
            self._finished = True
            self._publish(state)
