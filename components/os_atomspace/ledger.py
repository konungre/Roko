"""Durable representation ledger for OS-owner built facts; no OS executor exists here."""
import json
import os
from pathlib import Path
import sqlite3

from components.os_atomspace.contract import canonical,digest
from components.os_atomspace.os_fact_v1 import import_built_fact


class LedgerError(ValueError):pass


class Ledger:
    def __init__(self,path):
        path=Path(path)
        if not path.is_absolute() or path.resolve()!=path or path.is_symlink():
            raise LedgerError('Require canonical absolute ledger path')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        stat=path.parent.stat()
        if stat.st_uid!=os.geteuid() or stat.st_mode & 0o077:
            raise LedgerError('Require private owner-controlled ledger directory')
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None)
        try:
            version=self.db.execute('PRAGMA user_version').fetchone()[0]
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not ((version==0 and not tables) or (version==1 and tables=={'facts','heads'})):
                raise LedgerError('Unknown OS-state ledger schema')
            os.chmod(path,0o600)
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            if version==0 and not tables:
                self.db.executescript('''BEGIN IMMEDIATE;
                    CREATE TABLE facts(machine TEXT NOT NULL,backend TEXT NOT NULL,revision INTEGER NOT NULL,
                        stage TEXT NOT NULL,generation TEXT NOT NULL,fact_sha256 TEXT NOT NULL,
                        fact_hex TEXT NOT NULL,receipt_hex TEXT NOT NULL,source_commit TEXT NOT NULL,
                        PRIMARY KEY(machine,backend,revision));
                    CREATE TABLE heads(machine TEXT NOT NULL,backend TEXT NOT NULL,revision INTEGER NOT NULL,
                        fact_sha256 TEXT NOT NULL,PRIMARY KEY(machine,backend));
                    PRAGMA user_version=1;COMMIT;''')
        except BaseException as error:
            try:self.db.close()
            except BaseException as cleanup:error.close_error=repr(cleanup)
            raise

    def close(self):self.db.close()

    def ingest_built(self,fact_raw,receipt_raw,source_commit,*,expected_revision):
        if type(expected_revision) is not int or expected_revision<0:
            raise LedgerError('Explicit expected revision required')
        packet=import_built_fact(fact_raw,receipt_raw,source_commit)
        fact=packet['facts'][0]['value']['source_fact'];fact_sha=digest(fact)
        key=(fact['machine'],fact['backend']);revision=fact['revision']
        self.db.execute('BEGIN IMMEDIATE')
        try:
            existing=self.db.execute('SELECT fact_hex,receipt_hex,source_commit,fact_sha256,stage,generation FROM facts WHERE machine=? AND backend=? AND revision=?',
                                     (*key,revision)).fetchone()
            if existing is not None:
                if existing!=(fact_raw.hex(),receipt_raw.hex(),source_commit,fact_sha,fact['stage'],fact['generation']):
                    raise LedgerError('OS fact revision conflict')
                status='replayed'
            else:
                head=self.db.execute('SELECT revision,fact_sha256 FROM heads WHERE machine=? AND backend=?',key).fetchone() or (0,'0'*64)
                if expected_revision!=head[0]:raise LedgerError('Stale OS-state revision')
                if revision!=head[0]+1 or fact['predecessor']!=head[1]:
                    raise LedgerError('OS fact predecessor/revision mismatch')
                self.db.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?)',
                    (*key,revision,fact['stage'],fact['generation'],fact_sha,fact_raw.hex(),receipt_raw.hex(),source_commit))
                self.db.execute('INSERT INTO heads VALUES(?,?,?,?) ON CONFLICT(machine,backend) DO UPDATE SET revision=excluded.revision,fact_sha256=excluded.fact_sha256',
                    (*key,revision,fact_sha))
                status='ingested'
            self.db.execute('COMMIT')
        except BaseException as error:
            try:self.db.execute('ROLLBACK')
            except BaseException as cleanup:error.rollback_error=repr(cleanup)
            raise
        return {'schema':'roko.os-state.ledger.v1','status':status,'machine':key[0],'backend':key[1],
                'revision':revision,'fact_sha256':fact_sha,'stage':'built',
                'verified_native_os_state':False,'mutation_authority':False,'executed_actions':0}

    def snapshot(self,machine,backend):
        # One read transaction prevents a head from being paired with another
        # writer's fact rows. Recheck stored bytes before publication to PeTTa.
        self.db.execute('BEGIN')
        try:
            head=self.db.execute('SELECT revision,fact_sha256 FROM heads WHERE machine=? AND backend=?',(machine,backend)).fetchone()
            rows=self.db.execute('SELECT revision,fact_sha256,fact_hex,receipt_hex,source_commit,stage,generation FROM facts WHERE machine=? AND backend=? ORDER BY revision',
                                 (machine,backend)).fetchall()
            previous='0'*64;latest=None
            for index,(revision,fact_sha,fact_hex,receipt_hex,source_commit,stage,generation) in enumerate(rows,1):
                packet=import_built_fact(bytes.fromhex(fact_hex),bytes.fromhex(receipt_hex),source_commit)
                fact=packet['facts'][0]['value']['source_fact']
                if (fact['machine']!=machine or fact['backend']!=backend or fact['revision']!=index or revision!=index
                        or fact['predecessor']!=previous or digest(fact)!=fact_sha
                        or fact['stage']!=stage or fact['generation']!=generation):
                    raise LedgerError('Stored OS-state chain/identity mismatch')
                previous=fact_sha;latest=packet
            if (head is None and rows) or (head is not None and head!=(len(rows),previous)):
                raise LedgerError('Stored OS-state head mismatch')
            self.db.execute('COMMIT')
        except BaseException as error:
            try:self.db.execute('ROLLBACK')
            except BaseException as cleanup:error.rollback_error=repr(cleanup)
            raise
        return {'revision':len(rows),'head_sha256':previous,'packet':latest,
                'verified_native_os_state':False,'mutation_authority':False}
