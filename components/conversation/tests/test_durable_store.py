"""Real SQLite persistence, competing processes, and crash-recovery semantics."""
import json
import os
from pathlib import Path
import stat
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


if __name__=='__main__':unittest.main()
