"""Local durable fact snapshots with compare-and-swap; no execution authority."""
import json,sqlite3
from facts import Fact,digest
class Ledger:
 def __init__(self,path):
  self.db=sqlite3.connect(path,isolation_level=None)
  self.db.execute('PRAGMA synchronous=FULL')
  self.db.execute('CREATE TABLE IF NOT EXISTS facts(machine TEXT, backend TEXT, revision INTEGER, hash TEXT, body TEXT, mode TEXT, PRIMARY KEY(machine,backend,revision))')
 def append(self,fact,expected_revision,mode='observed'):
  if not isinstance(fact,Fact) or mode not in ('observed','simulation'):raise ValueError('typed fact and evidence mode required')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   row=self.db.execute('SELECT revision,hash FROM facts WHERE machine=? AND backend=? ORDER BY revision DESC LIMIT 1',(fact.machine,fact.backend)).fetchone()
   current,previous=row if row else (0,'0'*64)
   if expected_revision!=current or fact.revision!=current+1 or fact.predecessor!=previous:raise ValueError('stale revision or broken provenance')
   body={'fact':fact.document(),'mode':mode};identity=digest(body)
   self.db.execute('INSERT INTO facts VALUES(?,?,?,?,?,?)',(fact.machine,fact.backend,fact.revision,identity,json.dumps(body,sort_keys=True),mode))
   self.db.execute('COMMIT');return identity
  except BaseException:self.db.execute('ROLLBACK');raise
 def latest(self,machine,backend):
  rows=self.db.execute('SELECT body,hash,revision,mode FROM facts WHERE machine=? AND backend=? ORDER BY revision',(machine,backend)).fetchall()
  previous='0'*64
  for expected,(raw,identity,revision,mode) in enumerate(rows,1):
   body=json.loads(raw);f=dict(body['fact'])
   if body['mode']!=mode or mode not in ('observed','simulation') or digest(body)!=identity:raise ValueError('fact receipt corruption')
   if f.pop('schema')!='roko-os-fact-v1':raise ValueError('fact schema')
   from facts import Stage
   f['stage']=Stage(f['stage']);fact=Fact(**f)
   if (fact.machine,fact.backend,fact.revision,revision,fact.predecessor)!=(machine,backend,expected,expected,previous):raise ValueError('broken fact chain')
   previous=identity
  return (json.loads(rows[-1][0]),rows[-1][1]) if rows else None
 def close(self):self.db.close()
