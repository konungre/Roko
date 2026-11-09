"""Durable host-owned history and native-only turn index; no action dispatch.

SQLite is the history store, not MORK. Native retrieval indexes the latest 16
turns; authoritative history is never silently evicted to fit that index.
Session identifiers are namespaces, not authentication. Only the trusted host
may choose paths, sessions, request IDs, admission policy and runtime settings.
"""
import hashlib
import json
import sqlite3
import time

import native_mork
from durable_memory import _text

MAX_TURNS = 32
MAX_HISTORY_BYTES = 65536
MAX_TURN_BYTES = 4096
MAX_REQUESTS = 64


class RevisionConflict(RuntimeError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def _revision(value):
    if type(value) is not int or not 0 <= value <= MAX_TURNS:
        raise ValueError('Invalid conversation revision')
    return value


class ConversationStore:
    def __init__(self, path, *, native_backend=None):
        # Host-owned backend object. The default retains all historical pins.
        self._native_backend = native_mork if native_backend is None else native_backend
        self.db = sqlite3.connect(path, timeout=3)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS conversation_turns (
                session TEXT NOT NULL, sequence INTEGER NOT NULL,
                admission_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT NOT NULL,
                created_ns INTEGER NOT NULL,
                PRIMARY KEY(session, sequence), UNIQUE(session, admission_id));
            CREATE TABLE IF NOT EXISTS conversation_requests (
                session TEXT NOT NULL, request_id TEXT NOT NULL,
                revision INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                state TEXT NOT NULL, receipt TEXT, response TEXT,
                PRIMARY KEY(session, request_id));
        ''')

    def close(self):
        self.db.close()

    def _snapshot(self, session):
        rows = self.db.execute('''SELECT sequence, admission_id, role, content,
            source, created_ns FROM conversation_turns WHERE session=?
            ORDER BY sequence''', (session,)).fetchall()
        turns = [{'id': 't' + format(r[0], '012d'), 'sequence': r[0],
                  'admission_id': r[1], 'role': r[2], 'content': r[3],
                  'source': r[4], 'created_ns': r[5],
                  'sha256': hashlib.sha256(r[3].encode('utf-8')).hexdigest()}
                 for r in rows]
        return {'session': session, 'revision': len(turns), 'turns': turns,
                'history_sha256': _digest(turns)}

    def snapshot(self, session):
        return self._snapshot(_text(session, 128))

    def _insert(self, snapshot, admission_id, role, content, source):
        if snapshot['revision'] >= MAX_TURNS or sum(
                len(t['content'].encode('utf-8')) for t in snapshot['turns']) + len(
                content.encode('utf-8')) > MAX_HISTORY_BYTES:
            raise ValueError('History capacity exhausted; no turns were evicted')
        self.db.execute('INSERT INTO conversation_turns VALUES (?, ?, ?, ?, ?, ?, ?)',
            (snapshot['session'], snapshot['revision'], admission_id, role,
             content, source, time.time_ns()))

    def append(self, session, *, admission_id, role, content, source,
               expected_revision):
        """Explicit trusted-host admission, idempotent only for identical data."""
        session, admission_id = _text(session, 128), _text(admission_id, 128)
        if admission_id.startswith(('response:', 'request:')):
            raise ValueError('Reserved response admission ID')
        content, source = _text(content, MAX_TURN_BYTES), _text(source, 512)
        expected_revision = _revision(expected_revision)
        if type(role) is not str or role not in ('user', 'assistant'):
            raise ValueError('Only user/assistant text may enter history')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            snap = self._snapshot(session)
            old = next((t for t in snap['turns'] if t['admission_id'] == admission_id), None)
            if old:
                if (old['sequence'], old['role'], old['content'], old['source']) != (
                        expected_revision, role, content, source):
                    raise RevisionConflict('Admission ID is already bound to different data')
                return old['id']
            if snap['revision'] != expected_revision:
                raise RevisionConflict('Conversation changed; reload before admission')
            self._insert(snap, admission_id, role, content, source)
            return 't' + format(expected_revision, '012d')

    def prepare(self, session, *, request_id, expected_revision, role=None, timeout=3,
                _pending_user=None):
        """Return complete history plus native retrieval receipt, or raise.

        A failed native call is durably marked failed and yields no receipt.
        Pending/failed requests require a fresh request ID, including after a
        crash. Successful identical retries reuse their saved receipt.
        """
        session, request_id = _text(session, 128), _text(request_id, 128)
        expected_revision = _revision(expected_revision)
        if _pending_user is not None:
            if type(_pending_user) is not dict or set(_pending_user) != {'content', 'source'}:
                raise ValueError('Invalid staged user message')
            _pending_user = {'content': _text(_pending_user['content'], MAX_TURN_BYTES),
                             'source': _text(_pending_user['source'], 512)}
        if role is not None and (type(role) is not str or role not in ('user', 'assistant')):
            raise ValueError('Invalid turn-role query')
        query = {'relation': 'chat_turn', 'args': [None, role]}
        native_mork._validate([], query, timeout)
        fingerprint = _digest([expected_revision, query, timeout, _pending_user])
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            snap = self._snapshot(session)
            if snap['revision'] != expected_revision:
                raise RevisionConflict('Conversation changed before retrieval')
            if _pending_user is not None and (snap['revision'] + 2 > MAX_TURNS or sum(
                    len(t['content'].encode('utf-8')) for t in snap['turns']) + len(
                    _pending_user['content'].encode('utf-8')) >= MAX_HISTORY_BYTES):
                raise ValueError('Insufficient capacity for a complete exchange')
            old = self.db.execute('''SELECT fingerprint, state, receipt
                FROM conversation_requests WHERE session=? AND request_id=?''',
                (session, request_id)).fetchone()
            if old:
                if old[0] != fingerprint or old[1] != 'prepared':
                    raise RevisionConflict('Request ID already used or incomplete')
                return json.loads(old[2])
            count = self.db.execute('SELECT count(*) FROM conversation_requests WHERE session=?',
                                    (session,)).fetchone()[0]
            if count >= MAX_REQUESTS:
                raise ValueError('Request capacity exhausted')
            self.db.execute('INSERT INTO conversation_requests VALUES (?, ?, ?, ?, ?, NULL, NULL)',
                            (session, request_id, expected_revision, fingerprint, 'pending'))
        indexed = snap['turns'][-native_mork.MAX_FACTS:]
        facts = [{'relation': 'chat_turn', 'args': [t['id'], t['role']]} for t in indexed]
        try:
            result = self._native_backend.query_facts(facts, query, timeout=timeout)
            matches = {f['args'][0] for f in result['facts']}
            receipt = {**snap, 'request_id': request_id, 'memory': result,
                'request_token': _digest([session, request_id, fingerprint, snap['history_sha256']]),
                'index_scope': 'latest-16-turns', 'indexed_turns': len(indexed),
                'evidence': [t for t in indexed if t['id'] in matches],
                'advisory_only': True, 'authorizes_actions': False,
                'messages': [{'role': t['role'], 'content': t['content']} for t in snap['turns']]}
            if _pending_user is not None:
                receipt['pending_user'] = _pending_user
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                if self._snapshot(session)['history_sha256'] != snap['history_sha256']:
                    raise RevisionConflict('Conversation changed during native retrieval')
                changed = self.db.execute('''UPDATE conversation_requests SET state='prepared', receipt=?
                    WHERE session=? AND request_id=? AND state='pending' AND fingerprint=?''',
                    (json.dumps(receipt, ensure_ascii=False), session, request_id, fingerprint)).rowcount
                if changed != 1:
                    raise RevisionConflict('Request was removed or changed during retrieval')
            return receipt
        except BaseException:
            with self.db:
                self.db.execute('''UPDATE conversation_requests SET state='failed'
                    WHERE session=? AND request_id=? AND state='pending' ''', (session, request_id))
            raise

    def accept_response(self, session, *, request_id, request_token, content):
        """Persist host-approved text against its prepared request; never execute it."""
        session, request_id = _text(session, 128), _text(request_id, 128)
        request_token = _text(request_token, 64)
        content = _text(content, MAX_TURN_BYTES)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('''SELECT revision, state, receipt, response
                FROM conversation_requests WHERE session=? AND request_id=?''',
                (session, request_id)).fetchone()
            if not row or not row[2] or json.loads(row[2])['request_token'] != request_token:
                raise RevisionConflict('Response is not bound to this request')
            if 'pending_user' in json.loads(row[2]):
                raise RevisionConflict('Use atomic exchange admission for this request')
            if row[1] == 'completed' and row[3] == content:
                return 't' + format(row[0], '012d')
            if not row or row[1] != 'prepared':
                raise RevisionConflict('No prepared request for this response')
            snap = self._snapshot(session)
            if snap['revision'] != row[0] or snap['history_sha256'] != json.loads(row[2])['history_sha256']:
                raise RevisionConflict('Stale response; conversation changed')
            self._insert(snap, 'response:' + request_id, 'assistant', content, 'provider-response')
            self.db.execute('''UPDATE conversation_requests SET state='completed', response=?
                WHERE session=? AND request_id=?''', (content, session, request_id))
            return 't' + format(row[0], '012d')

    def prepare_exchange(self, session, *, request_id, expected_revision, content,
                         source, timeout=3):
        """Stage a user turn; native history retrieval does not commit transcript."""
        pending = {'content': _text(content, MAX_TURN_BYTES), 'source': _text(source, 512)}
        return self.prepare(session, request_id=request_id, expected_revision=expected_revision,
                            timeout=timeout, _pending_user=pending)

    def accept_exchange(self, session, *, request_id, request_token, content):
        """Atomically commit staged user text and admitted assistant text."""
        session, request_id = _text(session, 128), _text(request_id, 128)
        request_token, content = _text(request_token, 64), _text(content, MAX_TURN_BYTES)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('''SELECT revision, state, receipt, response
                FROM conversation_requests WHERE session=? AND request_id=?''',
                (session, request_id)).fetchone()
            receipt = json.loads(row[2]) if row and row[2] else {}
            if receipt.get('request_token') != request_token or 'pending_user' not in receipt:
                raise RevisionConflict('No staged exchange bound to this response')
            if row[1] == 'completed' and row[3] == content:
                return row[0] + 2
            if row[1] != 'prepared':
                raise RevisionConflict('Exchange request is not prepared')
            snap = self._snapshot(session)
            if snap['revision'] != row[0] or snap['history_sha256'] != receipt['history_sha256']:
                raise RevisionConflict('Stale exchange response')
            pending = receipt['pending_user']
            suffix = hashlib.sha256(request_id.encode('utf-8')).hexdigest()
            self._insert(snap, 'request:' + suffix, 'user', pending['content'], pending['source'])
            self._insert(self._snapshot(session), 'response:' + suffix, 'assistant', content,
                         'provider-response')
            self.db.execute('''UPDATE conversation_requests SET state='completed', response=?
                WHERE session=? AND request_id=?''', (content, session, request_id))
            return row[0] + 2

    def abandon_open_requests(self, session):
        """For an exclusive host owner: discard staged text after failure/restart.

        Pending/prepared request IDs remain unusable; committed history and
        completed receipts remain. Acquire the host's session lease first.
        """
        session = _text(session, 128)
        with self.db:
            self.db.execute('''UPDATE conversation_requests SET state='failed', receipt=NULL
                WHERE session=? AND state IN ('pending','prepared')''', (session,))

    def forget(self, session):
        """Delete this namespace's history and receipts, not backups/device remnants."""
        session = _text(session, 128)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('DELETE FROM conversation_requests WHERE session=?', (session,))
            self.db.execute('DELETE FROM conversation_turns WHERE session=?', (session,))
