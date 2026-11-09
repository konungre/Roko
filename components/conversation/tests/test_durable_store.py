"""Real SQLite persistence, competing processes, and crash-recovery semantics."""
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from durable_store import Store, StoreError


class DurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'history.sqlite'
        self.store = Store(self.path)
        self.payload = {'text':'Remember the lighthouse.','context':[]}
        self.user = {'role':'user','content':self.payload['text']}
        self.assistant = {'role':'assistant','content':'I will remember the lighthouse.'}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def assert_code(self, code, action):
        with self.assertRaises(StoreError) as raised:
            action()
        self.assertEqual(raised.exception.code,code)

    def claim(self, request='r1', revision=0):
        return self.store.start('s1',request,revision,self.payload)

    def child(self, code):
        env = {**os.environ, 'PYTHONPATH':str(SOURCE),'PYTHONDONTWRITEBYTECODE':'1'}
        return subprocess.Popen([sys.executable,'-B','-u','-c',code,str(self.path)],env=env,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def test_commit_reopen_and_exact_replay_without_new_claim(self):
        claim = self.claim()
        self.assertEqual(claim['history'],[])
        response = self.store.commit(claim['token'],self.user,self.assistant,
                                     {'text':self.assistant['content'],'executed_actions':0})
        self.assertEqual(response['revision'],1)
        with Store(self.path) as reopened:
            replay = reopened.start('s1','r1',0,dict(context=[],text=self.payload['text']))
            self.assertEqual(replay,{'status':'replayed','response':response,'revision':1})
            self.assertEqual(reopened.snapshot('s1')['history'],[self.user,self.assistant])
        self.assert_code('invalid_token',lambda:self.store.commit(claim['token'],self.user,self.assistant,response))
        self.assert_code('stale_revision',lambda:self.claim('r2',0))
        second = self.claim('r2',1)
        self.assertEqual(second['history'],[self.user,self.assistant])
        self.store.fail(second['token'],{'code':'test-abandon'})

    def test_request_identity_rejects_changed_payload_or_revision(self):
        claim = self.claim()
        self.store.commit(claim['token'],self.user,self.assistant,{'text':self.assistant['content']})
        self.assert_code('request_conflict',lambda:self.store.start('s1','r1',0,{'text':'different'}))
        self.assert_code('request_conflict',lambda:self.store.start('s1','r1',1,self.payload))
        self.assertEqual(self.store.snapshot('s1')['revision'],1)

    def test_pending_is_never_retried_and_live_owner_cannot_recover(self):
        claim = self.claim()
        with Store(self.path) as second:
            self.assert_code('pending',lambda:second.start('s1','r1',0,self.payload))
            self.assert_code('busy',lambda:second.start('s1','r2',0,self.payload))
            self.assert_code('busy',lambda:second.recover('s1','r1',0))
        self.store.fail(claim['token'],{'code':'test-abandon'})

    def test_failed_turn_changes_neither_history_nor_revision(self):
        claim = self.claim()
        self.assert_code('invalid_commit',lambda:self.store.commit(claim['token'],
            {'role':'user','content':'different request'},self.assistant,{}))
        self.assert_code('invalid_commit',lambda:self.store.commit(claim['token'],self.user,self.assistant,{'text':'different answer'}))
        self.store.fail(claim['token'],{'code':'native-failed'})
        self.assertEqual(self.store.snapshot('s1'),{'revision':0,'history':[],'pending':None})
        self.assert_code('failed',lambda:self.claim())
        self.assert_code('invalid_token',lambda:self.store.commit(claim['token'],self.user,self.assistant,{}))
        fresh = self.claim('r2')
        self.assertEqual(fresh['history'],[])
        self.store.fail(fresh['token'],{})

    def test_process_crash_requires_explicit_recovery_then_new_request(self):
        proc = self.child("from durable_store import Store; import sys,json,os; s=Store(sys.argv[1]); c=s.start('s1','r1',0,{'text':'Remember the lighthouse.','context':[]}); print(json.dumps(c),flush=True); os._exit(9)")
        out,err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,9,err)
        dead_claim = json.loads(out)
        self.assert_code('pending',lambda:self.claim())
        self.assert_code('stale_revision',lambda:self.store.recover('s1','r1',1))
        self.assertEqual(self.store.recover('s1','r1',0),{'status':'interrupted','revision':0})
        self.assertEqual(self.store.snapshot('s1'),{'revision':0,'history':[],'pending':None})
        self.assert_code('interrupted',lambda:self.claim())
        self.assert_code('invalid_token',lambda:self.store.commit(dead_claim['token'],self.user,self.assistant,{}))
        new_claim=self.claim('r2')
        self.store.commit(new_claim['token'],self.user,self.assistant,{'text':self.assistant['content']})
        self.assertEqual(self.store.snapshot('s1')['revision'],1)

    def test_competing_processes_claim_only_one_revision(self):
        code="""from durable_store import Store,StoreError
import sys,json,time,os
s=Store(sys.argv[1])
try:
 c=s.start('s1','r'+str(os.getpid()),0,{'text':'hello','context':[]})
 print(json.dumps(c),flush=True)
 time.sleep(30)
except StoreError as e:
 print(json.dumps({'error':e.code}),flush=True)
"""
        processes=[self.child(code) for _ in range(5)]
        try:
            results=[json.loads(p.stdout.readline()) for p in processes]
            self.assertEqual(sum(r.get('status')=='claimed' for r in results),1,results)
            self.assertEqual(sum(r.get('error')=='busy' for r in results),4,results)
            self.assertEqual(self.store.snapshot('s1')['revision'],0)
            self.assertEqual(self.store.snapshot('s1')['history'],[])
        finally:
            for proc in processes:
                if proc.poll() is None:proc.kill()
                proc.communicate(timeout=5)

    def test_crash_inside_commit_rolls_back_history_and_response(self):
        code = """from durable_store import Store
import sys,os,json
s=Store(sys.argv[1]);c=s.start('s1','r1',0,{'text':'Remember the lighthouse.','context':[]})
class CrashAfterHistoryWrite:
 def execute(self,sql,*args):
  result=real.execute(sql,*args)
  if sql.startswith('UPDATE sessions SET history='): os._exit(17)
  return result
real=s.db;s.db=CrashAfterHistoryWrite()
s.commit(c['token'],{'role':'user','content':'Remember the lighthouse.'},{'role':'assistant','content':'Saved answer'},{'text':'Saved answer'})
"""
        proc=self.child(code);out,err=proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,17,err)
        self.assertEqual(self.store.snapshot('s1'),{'revision':0,'history':[],'pending':'r1'})
        self.assert_code('pending',lambda:self.claim())
        self.assertEqual(self.store.recover('s1','r1',0)['status'],'interrupted')

    def test_commit_survives_crash_before_response_delivery(self):
        code = """from durable_store import Store
import sys,os
s=Store(sys.argv[1]);c=s.start('s1','r1',0,{'text':'Remember the lighthouse.','context':[]})
s.commit(c['token'],{'role':'user','content':'Remember the lighthouse.'},{'role':'assistant','content':'Saved answer'},{'text':'Saved answer','executed_actions':0})
os._exit(19)
"""
        proc=self.child(code);out,err=proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,19,err)
        replay=self.claim()
        self.assertEqual(replay['status'],'replayed')
        self.assertEqual(replay['response'],{'text':'Saved answer','executed_actions':0,'revision':1})
        self.assertEqual(len(self.store.snapshot('s1')['history']),2)

    def test_database_and_sidecars_are_private(self):
        self.claim()
        for path in [self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')]:
            if path.exists():self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        link=Path(self.temp.name)/'link.sqlite';link.symlink_to(self.path)
        with self.assertRaises(OSError):Store(link)

    def test_invalid_revision_and_nonfinite_payload_make_no_session(self):
        for revision in (True,-1,'0'):
            self.assert_code('invalid_request',lambda:self.store.start('s1','r1',revision,self.payload))
        self.assert_code('invalid_request',lambda:self.store.start('s1','r1',0,{'value':float('nan')}))
        self.assertEqual(self.store.snapshot('s1'),{'revision':0,'history':[],'pending':None})

    def test_legacy_database_migration_preserves_history_revisions_and_replays(self):
        legacy = Path(self.temp.name)/'legacy.sqlite'
        history = [self.user,self.assistant]
        response = {'text':self.assistant['content'],'revision':7,'executed_actions':0}
        with sqlite3.connect(legacy) as db:
            db.executescript('''
              CREATE TABLE sessions(id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                                    history TEXT NOT NULL,pending TEXT);
              CREATE TABLE requests(session_id TEXT NOT NULL REFERENCES sessions(id),
                request_id TEXT NOT NULL,expected_revision INTEGER NOT NULL,
                payload TEXT NOT NULL,payload_sha256 TEXT NOT NULL,status TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,owner TEXT NOT NULL,response TEXT,error TEXT,
                created_ns INTEGER NOT NULL,completed_ns INTEGER,
                PRIMARY KEY(session_id,request_id));
            ''')
            db.execute('INSERT INTO sessions VALUES (?,?,?,NULL)',('s1',7,json.dumps(history)))
            payload=json.dumps(self.payload,sort_keys=True,separators=(',',':'))
            db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('s1','old',6,payload,'retained-digest','committed','retained-token',
                        '{}',json.dumps(response),None,1,2))
            before=db.execute('SELECT * FROM requests').fetchall()
        with Store(legacy) as migrated:
            self.assertEqual(migrated.snapshot('s1'),{'revision':7,'history':history,'pending':None})
            self.assertEqual(migrated.snapshot('s1',include_cognition=True)['cognitive_history'],[])
            replay=migrated.start('s1','old',6,self.payload)
            self.assertEqual(replay['response'],response)
            self.assertEqual([tuple(row) for row in migrated.db.execute('SELECT * FROM requests')],before)
            claim=migrated.start('s1','new',7,self.payload)
            self.assertEqual(claim['cognitive_history'],[])
            migrated.fail(claim['token'],{})
        # Opening an already migrated database is idempotent.
        with Store(legacy) as reopened:
            self.assertEqual(reopened.snapshot('s1')['revision'],7)
            self.assertEqual(len([row for row in reopened.db.execute('PRAGMA table_info(sessions)')
                                  if row['name']=='cognitive_history']),1)

    def test_cognitive_ledger_survives_restart_and_omitted_updates(self):
        observations=[{'id':'nars_turn_1','text':'Uncertain robin -> animal belief.'}]
        claim=self.claim()
        self.assertEqual(claim['cognitive_history'],[])
        response=self.store.commit(claim['token'],self.user,self.assistant,
                                   {'text':self.assistant['content']},cognitive_history=observations)
        with Store(self.path) as reopened:
            self.assertNotIn('cognitive_history',reopened.snapshot('s1'))
            self.assertEqual(reopened.snapshot('s1',include_cognition=True)['cognitive_history'],observations)
            self.assertEqual(reopened.start('s1','r1',0,self.payload)['response'],response)
            second=reopened.start('s1','r2',1,self.payload)
            self.assertEqual(second['cognitive_history'],observations)
            reopened.commit(second['token'],self.user,self.assistant,{'text':self.assistant['content']})
            self.assertEqual(reopened.snapshot('s1',include_cognition=True)['cognitive_history'],observations)
            third=reopened.start('s1','r3',2,self.payload)
            reopened.fail(third['token'],{'code':'native-failure'})
            self.assertEqual(reopened.snapshot('s1',include_cognition=True)['cognitive_history'],observations)

    def test_concurrent_workers_migrate_legacy_schema_once(self):
        self.store.db.execute('ALTER TABLE sessions DROP COLUMN cognitive_history')
        code="""from durable_store import Store
import sys,json
with Store(sys.argv[1]) as s: print(json.dumps(s.snapshot('s1',include_cognition=True)),flush=True)
"""
        processes=[self.child(code) for _ in range(5)]
        for proc in processes:
            out,err=proc.communicate(timeout=10)
            self.assertEqual(proc.returncode,0,err)
            self.assertEqual(json.loads(out),{'revision':0,'history':[],'pending':None,'cognitive_history':[]})
        self.assertEqual(sum(row['name']=='cognitive_history' for row in
                             self.store.db.execute('PRAGMA table_info(sessions)')),1)

    def test_invalid_cognition_does_not_commit_or_replace_ledger(self):
        claim=self.claim()
        invalid=[{},'text',[{'id':'x','text':'y','extra':0}],
                 [{'id':'','text':'y'}],[{'id':'x','text':' '}],
                 [{'id':'x'*129,'text':'y'}],[{'id':'x','text':'y'*501}],
                 [{'id':'x','text':'y'},{'id':'x','text':'z'}],
                 [{'id':str(i),'text':'y'} for i in range(257)]]
        for observations in invalid:
            self.assert_code('invalid_commit',lambda:self.store.commit(claim['token'],self.user,self.assistant,
                {'text':self.assistant['content']},cognitive_history=observations))
        self.assertEqual(self.store.snapshot('s1',include_cognition=True),
                         {'revision':0,'history':[],'pending':'r1','cognitive_history':[]})
        self.store.fail(claim['token'],{})

    def test_crash_rolls_back_cognition_and_history_together(self):
        first=[{'id':'nars_turn_1','text':'Prior admitted belief.'}]
        c=self.claim();self.store.commit(c['token'],self.user,self.assistant,{},cognitive_history=first)
        code="""from durable_store import Store
import sys,os
s=Store(sys.argv[1]);c=s.start('s1','r2',1,{'text':'Remember the lighthouse.','context':[]})
class CrashAfterHistoryWrite:
 def execute(self,sql,*args):
  result=real.execute(sql,*args)
  if sql.startswith('UPDATE sessions SET history='): os._exit(23)
  return result
real=s.db;s.db=CrashAfterHistoryWrite()
s.commit(c['token'],{'role':'user','content':'Remember the lighthouse.'},
 {'role':'assistant','content':'Unsaved answer'},{'text':'Unsaved answer'},
 cognitive_history=[{'id':'nars_turn_1','text':'Prior admitted belief.'},
                    {'id':'nars_turn_2','text':'Uncommitted new belief.'}])
"""
        proc=self.child(code);out,err=proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,23,err)
        snapshot=self.store.snapshot('s1',include_cognition=True)
        self.assertEqual(snapshot,{'revision':1,'history':[self.user,self.assistant],
                                   'pending':'r2','cognitive_history':first})
        self.store.recover('s1','r2',1)
        snapshot=self.store.snapshot('s1',include_cognition=True)
        self.assertEqual(snapshot['cognitive_history'],first)
        self.assertEqual(snapshot['revision'],1)
        self.assertIsNone(snapshot['pending'])

    def test_committed_cognition_survives_crash_before_delivery(self):
        code="""from durable_store import Store
import sys,os
s=Store(sys.argv[1]);c=s.start('s1','r1',0,{'text':'Remember the lighthouse.','context':[]})
s.commit(c['token'],{'role':'user','content':'Remember the lighthouse.'},
 {'role':'assistant','content':'Saved answer'},{'text':'Saved answer'},
 cognitive_history=[{'id':'nars_turn_1','text':'Committed belief.'}])
os._exit(29)
"""
        proc=self.child(code);out,err=proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,29,err)
        replay=self.claim()
        self.assertEqual(replay['response'],{'text':'Saved answer','revision':1})
        self.assertEqual(self.store.snapshot('s1',include_cognition=True)['cognitive_history'],
                         [{'id':'nars_turn_1','text':'Committed belief.'}])


if __name__=='__main__':unittest.main()
