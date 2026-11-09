"""Durable userspace boot-trial protocol; no bootloader or firmware writes.

The journal lives in trusted owned private storage. It selects descriptors only.
A boot adapter must authenticate actual slot bytes before boot and bind health
confirmation to the current boot; neither is supplied by this module.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def descriptor(value):
    if type(value) is not dict or set(value) != {'slot', 'sequence', 'sha256'}:
        raise ValueError('Invalid slot descriptor')
    if value['slot'] not in ('A', 'B') or type(value['sequence']) is not int or not 1 <= value['sequence'] < 2**63:
        raise ValueError('Invalid slot or sequence')
    if type(value['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', value['sha256']):
        raise ValueError('Invalid slot digest')
    return value


def validate(state):
    if type(state) is not dict or set(state) != {'schema','revision','good','trial','attempts_left','active_nonce'}:
        raise ValueError('Invalid journal schema')
    if state['schema'] != 'roko-boot-trial-v1' or type(state['revision']) is not int or state['revision'] < 0:
        raise ValueError('Invalid journal revision')
    descriptor(state['good'])
    remaining = state['attempts_left']
    if type(remaining) is not int or not 0 <= remaining <= 3:
        raise ValueError('Invalid attempt budget')
    nonce = state['active_nonce']
    if nonce is not None and (type(nonce) is not str or not re.fullmatch('[0-9a-f]{32}', nonce)):
        raise ValueError('Invalid boot nonce')
    trial = state['trial']
    if trial is None:
        if remaining or nonce is not None: raise ValueError('Trial metadata without trial')
    else:
        descriptor(trial)
        if trial['slot'] == state['good']['slot'] or trial['sequence'] <= state['good']['sequence']:
            raise ValueError('Trial must be newer and use the inactive slot')
    return state


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        info = self.directory.lstat()
        if (self.directory != self.directory.resolve() or not stat.S_ISDIR(info.st_mode) or
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Private owned canonical journal directory required')
        self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.lock = os.open('lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self.fd)
            info = os.fstat(self.lock)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Invalid journal lock')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            if hasattr(self,'lock'): os.close(self.lock)
            os.close(self.fd)
            raise

    def close(self):
        os.close(self.lock); os.close(self.fd)

    def read(self):
        fd = os.open('state.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096:
                raise ValueError('Invalid journal file')
            raw = stream.read(4097)
        state = validate(json.loads(raw))
        if encoded(state) != raw: raise ValueError('Noncanonical or duplicate-key journal')
        return state

    def write(self, state, checkpoint=lambda phase: None):
        raw = encoded(validate(state))
        name = '.transaction-'+secrets.token_hex(16)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        checkpoint('file-durable')
        os.replace(name, 'state.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
        checkpoint('state-published')
        os.fsync(self.fd)
        checkpoint('directory-durable')

    def initialize(self, good):
        # Must never reset an existing journal, including a corrupt one.
        try: os.stat('state.json', dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError: pass
        else: raise FileExistsError('Journal already initialized')
        state = {'schema':'roko-boot-trial-v1','revision':0,'good':descriptor(good),
                 'trial':None,'attempts_left':0,'active_nonce':None}
        self.write(state)
        return state

    def transition(self, action, expected_revision, *, candidate=None, nonce=None, checkpoint=lambda phase: None):
        state = self.read()
        if type(expected_revision) is not int or state['revision'] != expected_revision:
            raise ValueError('Stale journal revision')
        selected = None
        if action == 'arm':
            if state['trial'] is not None: raise ValueError('Trial already pending')
            state.update(trial=descriptor(candidate), attempts_left=3, active_nonce=None)
        elif action == 'select':
            if state['trial'] is not None and state['attempts_left']:
                state['attempts_left'] -= 1
                state['active_nonce'] = secrets.token_hex(16)
                selected = state['trial']
            else:
                state.update(trial=None, attempts_left=0, active_nonce=None)
                selected = state['good']
        elif action == 'confirm':
            if state['trial'] is None or nonce is None or nonce != state['active_nonce']:
                raise ValueError('Confirmation must match the active trial boot')
            state.update(good=state['trial'], trial=None, attempts_left=0, active_nonce=None)
        elif action == 'abort':
            state.update(trial=None, attempts_left=0, active_nonce=None)
        else:
            raise ValueError('Unknown journal transition')
        state['revision'] += 1
        self.write(state, checkpoint)
        return {'state':state,'selected':selected,'boot_executed':False}
