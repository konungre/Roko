"""Transactional local conversation history; inference is outside the transaction.

The database path is trusted launcher configuration, never request data. Claims
survive crashes and require explicit recovery. A replay returns the saved response
without inference; a token can commit at most once. SQLite WAL + FULL synchronous
provides local durability subject to the underlying filesystem/storage guarantees.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid
from contextlib import contextmanager


class StoreError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise StoreError('invalid_request', 'Expected finite JSON data') from error


def _identifier(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value) is None:
        raise StoreError('invalid_request', 'Invalid session or request identifier')
    return value


def _revision(value):
    if type(value) is not int or not 0 <= value < 2**63-1:
        raise StoreError('invalid_request', 'Expected nonnegative integer revision')
    return value


def _identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return {'pid': pid, 'start': fields[19],
                'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'namespace': os.readlink(f'/proc/{pid}/ns/pid')}
    except FileNotFoundError:
        return None
    except (OSError, IndexError, ValueError) as error:
        raise StoreError('unavailable', 'Cannot verify claim owner identity') from error


def _alive(owner):
    return _identity(owner['pid']) == owner


class Store:
    def __init__(self, path):
        self.path = Path(path).absolute()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise StoreError('unsafe_path', 'Database must be a regular file owned by this user')
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        parent_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                history TEXT NOT NULL, pending TEXT
            );
            CREATE TABLE IF NOT EXISTS requests (
                session_id TEXT NOT NULL REFERENCES sessions(id),
                request_id TEXT NOT NULL, expected_revision INTEGER NOT NULL,
                payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
                owner TEXT NOT NULL, response TEXT, error TEXT,
                created_ns INTEGER NOT NULL, completed_ns INTEGER,
                PRIMARY KEY(session_id,request_id)
            );
        ''')
        for sidecar in (str(self.path)+'-wal', str(self.path)+'-shm'):
            if os.path.exists(sidecar):
                os.chmod(sidecar, 0o600)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def start(self, session_id, request_id, expected_revision, payload):
        session_id, request_id = _identifier(session_id), _identifier(request_id)
        _revision(expected_revision)
        if type(payload) is not dict:
            raise StoreError('invalid_request', 'Payload must be an object')
        encoded = _json(payload)
        owner = _identity(os.getpid())
        if owner is None:
            raise StoreError('unavailable', 'Cannot establish claim owner identity')
        with self._transaction():
            prior = self.db.execute('SELECT * FROM requests WHERE session_id=? AND request_id=?',
                                    (session_id, request_id)).fetchone()
            if prior:
                if prior['payload'] != encoded or prior['expected_revision'] != expected_revision:
                    raise StoreError('request_conflict', 'Request identifier already binds different input')
                if prior['status'] == 'committed':
                    return {'status':'replayed', 'response':json.loads(prior['response']),
                            'revision':prior['expected_revision']+1}
                raise StoreError(prior['status'], 'Request is '+prior['status']+'; never automatically rerun')
            session = self.db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
            if session is None:
                if expected_revision != 0:
                    raise StoreError('stale_revision', 'New session starts at revision zero')
                self.db.execute('INSERT INTO sessions VALUES (?,0,?,NULL)', (session_id, '[]'))
                history, revision = [], 0
            else:
                if session['revision'] != expected_revision:
                    raise StoreError('stale_revision', 'Session revision changed')
                if session['pending'] is not None:
                    raise StoreError('busy', 'Session has an unresolved request')
                history, revision = json.loads(session['history']), session['revision']
            token = uuid.uuid4().hex
            self.db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,NULL,NULL,?,NULL)',
                            (session_id, request_id, expected_revision, encoded,
                             hashlib.sha256(encoded.encode()).hexdigest(), 'pending', token,
                             _json(owner), time.time_ns()))
            self.db.execute('UPDATE sessions SET pending=? WHERE id=?', (request_id, session_id))
            return {'status':'claimed', 'token':token, 'history':history, 'revision':revision}

    def _claim(self, token):
        if type(token) is not str:
            raise StoreError('invalid_token', 'Invalid claim token')
        request = self.db.execute('SELECT * FROM requests WHERE token=?', (token,)).fetchone()
        if request is None or request['status'] != 'pending':
            raise StoreError('invalid_token', 'Claim is not pending')
        session = self.db.execute('SELECT * FROM sessions WHERE id=?', (request['session_id'],)).fetchone()
        if session['pending'] != request['request_id'] or session['revision'] != request['expected_revision']:
            raise StoreError('stale_revision', 'Claim no longer owns this revision')
        return request, session

    def commit(self, token, user, assistant, response):
        for value, role in ((user,'user'), (assistant,'assistant')):
            if type(value) is not dict or set(value) != {'role','content'} or value['role'] != role or type(value['content']) is not str or not value['content'].strip():
                raise StoreError('invalid_commit', 'Expected exact user/assistant text messages')
        if type(response) is not dict:
            raise StoreError('invalid_commit', 'Response must be an object')
        with self._transaction():
            request, session = self._claim(token)
            payload = json.loads(request['payload'])
            if 'text' in payload and payload['text'] != user['content']:
                raise StoreError('invalid_commit', 'Committed user differs from claimed request')
            if 'text' in response and response['text'] != assistant['content']:
                raise StoreError('invalid_commit', 'Response differs from committed assistant text')
            saved = dict(response)
            saved['revision'] = session['revision']+1
            encoded_response = _json(saved)
            history = json.loads(session['history'])+[user,assistant]
            self.db.execute('UPDATE sessions SET history=?,revision=?,pending=NULL WHERE id=?',
                            (_json(history),saved['revision'],request['session_id']))
            self.db.execute("UPDATE requests SET status='committed',response=?,completed_ns=? WHERE token=?",
                            (encoded_response,time.time_ns(),token))
            return saved

    def fail(self, token, error):
        encoded = _json(error)
        with self._transaction():
            request, session = self._claim(token)
            self.db.execute("UPDATE requests SET status='failed',error=?,completed_ns=? WHERE token=?",
                            (encoded,time.time_ns(),token))
            self.db.execute('UPDATE sessions SET pending=NULL WHERE id=?', (request['session_id'],))
        return {'status':'failed','revision':session['revision']}

    def recover(self, session_id, request_id, expected_revision):
        """Explicitly abandon a dead owner's pending claim; never invoke inference."""
        session_id, request_id = _identifier(session_id), _identifier(request_id)
        _revision(expected_revision)
        with self._transaction():
            session = self.db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
            if session is None or session['revision'] != expected_revision:
                raise StoreError('stale_revision', 'Session revision changed or is absent')
            request = self.db.execute('SELECT * FROM requests WHERE session_id=? AND request_id=?',
                                    (session_id,request_id)).fetchone()
            if request and request['expected_revision'] != expected_revision:
                raise StoreError('stale_revision', 'Request was bound to a different revision')
            if request and request['status']=='interrupted':
                return {'status':'interrupted','revision':session['revision']}
            if request is None or request['status']!='pending' or session['pending']!=request_id:
                raise StoreError('not_pending', 'Requested claim is not pending')
            if _alive(json.loads(request['owner'])):
                raise StoreError('busy', 'Claim owner is still alive; cancel and wait before recovery')
            self.db.execute("UPDATE requests SET status='interrupted',error=?,completed_ns=? WHERE token=?",
                            (_json({'code':'explicit_recovery'}),time.time_ns(),request['token']))
            self.db.execute('UPDATE sessions SET pending=NULL WHERE id=?', (session_id,))
            return {'status':'interrupted','revision':session['revision']}

    def snapshot(self, session_id):
        _identifier(session_id)
        row = self.db.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
        if row is None:
            return {'revision':0,'history':[],'pending':None}
        return {'revision':row['revision'],'history':json.loads(row['history']),'pending':row['pending']}
