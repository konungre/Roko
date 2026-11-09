"""Bounded cosmetic state and movement; never an authorization channel."""
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import time

STATES = {'idle': 'idle', 'thinking': 'running', 'waiting': 'waiting',
          'review': 'review', 'failed': 'failed', 'complete': 'waving'}
MAX_BYTES = 1024
TTL = 15

def validate_event(event, now=None):
    now = time.time() if now is None else now
    if not isinstance(event, dict) or set(event) != {'version', 'state', 'time'}:
        raise ValueError('Expected version, state and time only')
    if type(event['version']) is not int or event['version'] != 1 or not isinstance(event['state'],str) or event['state'] not in STATES:
        raise ValueError('Invalid event version or state')
    stamp = event['time']
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp > now + 2 or now - stamp > TTL:
        raise ValueError('Invalid or stale event timestamp')
    return event['state']

def read_event(path, now=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_BYTES:
            raise ValueError('Event must be a small regular file owned by this user')
        raw = os.read(fd, MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Oversized event')
        return validate_event(json.loads(raw), now)
    finally:
        os.close(fd)

def publish_event(path, state, now=None):
    """Caller supplies an existing private directory. Atomic last-value publication."""
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
        if os.path.exists(temp): os.unlink(temp)

class Motion:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.direction = 1
        self.crawl = False
        self.paused = False
    def bound(self, width, height):
        self.x = max(0, min(self.x, max(0,width-192)))
        self.y = max(0, min(self.y, max(0,height-208)))
    def step(self, dt, width, height):
        if self.crawl and not self.paused:
            self.x += self.direction * 55 * max(0,min(dt,0.1))
            if self.x >= max(0,width-192): self.direction = -1
            if self.x <= 0: self.direction = 1
        self.bound(width,height)
    def drag(self, dx, dy, width, height):
        self.x += dx
        self.y += dy
        self.bound(width,height)
