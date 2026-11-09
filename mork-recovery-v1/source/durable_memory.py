"""Durable typed evidence for a conversational adapter; SQLite is not MORK.

The caller must admit facts explicitly. Retrieval always uses native_mork and
propagates its failure. Returned evidence is data, never action authority.
"""
import hashlib
import json
import sqlite3
import time

import native_mork


def _text(value, limit):
    if type(value) is not str or not value or len(value.encode('utf-8')) > limit:
        raise ValueError('Invalid bounded provenance field')
    return value


class DurableMemory:
    """Open a caller-owned private database; no automatic conversation capture.

    Session IDs are namespaces, not authentication. The trusted host controls
    access to this object and its path. Only 16 evidence records per session
    are admitted, matching the native adapter's bounded fact contract.
    """

    def __init__(self, path, *, native_backend=None):
        # Explicit trusted-host selection only; never supplied by model output.
        self._native_backend = native_mork if native_backend is None else native_backend
        self.db = sqlite3.connect(path, timeout=3)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('''CREATE TABLE IF NOT EXISTS evidence (
            session TEXT NOT NULL, id TEXT NOT NULL, fact TEXT NOT NULL,
            source TEXT NOT NULL, turn TEXT NOT NULL, created_ns INTEGER NOT NULL,
            PRIMARY KEY (session, id))''')
        self.db.commit()

    def close(self):
        self.db.close()

    def remember(self, session, fact, *, source, turn):
        session = _text(session, 128)
        source, turn = _text(source, 512), _text(turn, 128)
        fact = native_mork._row(fact)
        encoded = json.dumps(fact, sort_keys=True, separators=(',', ':'))
        identity = json.dumps([session, fact, source, turn], sort_keys=True,
                              separators=(',', ':')).encode('utf-8')
        record_id = hashlib.sha256(identity).hexdigest()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            rows = self.db.execute('SELECT id, fact FROM evidence WHERE session=?',
                                   (session,)).fetchall()
            if any(row[0] == record_id for row in rows):
                return record_id
            facts = [json.loads(row[1]) for row in rows] + [fact]
            native_mork._validate(facts, fact, 3)
            self.db.execute('INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)',
                            (session, record_id, encoded, source, turn, time.time_ns()))
        return record_id

    def forget(self, session, record_id):
        session, record_id = _text(session, 128), _text(record_id, 64)
        with self.db:
            count = self.db.execute('DELETE FROM evidence WHERE session=? AND id=?',
                                    (session, record_id)).rowcount
        return count == 1

    def recall(self, session, query, *, timeout=3):
        session = _text(session, 128)
        rows = self.db.execute('''SELECT id, fact, source, turn, created_ns
            FROM evidence WHERE session=? ORDER BY created_ns, id''', (session,)).fetchall()
        facts = [json.loads(row[1]) for row in rows]
        result = self._native_backend.query_facts(facts, query, timeout=timeout)
        # Native output already passed independent completeness validation.
        evidence = [{'id': row[0], 'fact': fact, 'source': row[2],
                     'turn': row[3], 'created_ns': row[4]}
                    for row, fact in zip(rows, facts) if fact in result['facts']]
        return {**result, 'evidence': evidence, 'storage': 'sqlite',
                'trust': 'caller-supplied-evidence', 'authorizes_actions': False}
