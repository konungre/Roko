"""Atomic, revision-checked local checkpoints. Integrity is not authentication."""
import fcntl,hashlib,json,os,stat,tempfile,time,math
from pathlib import Path
from working_state import WorkingState
MAX_BYTES=1024*1024
class RevisionConflict(ValueError):pass
class CommitUncertain(OSError):pass
def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def unique(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('Duplicate JSON key')
  result[k]=v
 return result
def restore(payload):
 if type(payload) is not dict or set(payload)!={'task_id','goal','phase','evidence','proposal','verification','executed_actions'}:raise ValueError('Invalid state schema')
 if type(payload['executed_actions']) is not int or payload['executed_actions']!=0:raise ValueError('Checkpoint cannot assert executed actions')
 state=WorkingState(payload['task_id'],payload['goal'])
 if type(payload['evidence']) is not dict:raise ValueError('Invalid evidence map')
 for key,e in payload['evidence'].items():
  if type(e) is not dict or set(e)!={'source','text','sha256'}:raise ValueError('Invalid evidence schema')
  state.add_evidence(key,e['source'],e['text'])
  if state.snapshot()['evidence'][key]!=e:raise ValueError('Evidence digest mismatch')
 proposal=payload['proposal']
 if proposal is not None:
  if type(proposal) is not dict or set(proposal)!={'name','arguments','evidence_ids'}:raise ValueError('Invalid proposal schema')
  state.propose(state.task_id,proposal['name'],proposal['arguments'],proposal['evidence_ids'])
 if payload['verification'] is not None:
  verification=payload['verification']
  checkers={'strict-invoice-v1':state.verify_invoice,'exact-quote-v1':state.verify_quote,'integer-arithmetic-v1':state.verify_arithmetic}
  if type(verification) is not dict or verification.get('checker') not in checkers:raise ValueError('Unsupported verification checker')
  if checkers[verification['checker']]()!=verification:raise ValueError('Verification disagrees with current checker')
 if payload['phase']=='closed':state.close()
 if canonical(state.snapshot())!=canonical(payload):raise ValueError('Invalid phase or state contents')
 return state

class StateStore:
 def __init__(self,directory,*,lock_timeout=3):
  if type(lock_timeout) not in (int,float) or not math.isfinite(lock_timeout) or not 0<lock_timeout<=30:raise ValueError("Invalid lock timeout")
  self.lock_timeout=lock_timeout
  self.directory=Path(directory).resolve()
  if not self.directory.is_dir():raise ValueError('Existing trusted checkpoint directory required')
 def path(self,task_id):
  if type(task_id) is not str or not task_id or len(task_id)>128:raise ValueError('Invalid task ID')
  return self.directory/(hashlib.sha256(task_id.encode()).hexdigest()+'.json')
 def load(self,task_id):
  path=self.path(task_id)
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  try:
   if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('Checkpoint must be a regular file')
   with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(MAX_BYTES+1)
  finally:os.close(fd)
  if len(raw)>MAX_BYTES:raise ValueError('Checkpoint too large')
  data=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
  if type(data) is not dict or set(data)!={'version','revision','payload','sha256'}:raise ValueError('Invalid envelope')
  if type(data['version']) is not int or data['version']!=1:raise ValueError('Unsupported checkpoint version')
  if type(data['revision']) is not int or data['revision']<1:raise ValueError('Invalid revision')
  body={k:data[k] for k in ('version','revision','payload')}
  if hashlib.sha256(canonical(body)).hexdigest()!=data['sha256']:raise ValueError('Checkpoint digest mismatch')
  state=restore(data['payload'])
  if state.task_id!=task_id:raise ValueError('Cross-task checkpoint')
  return state,data['revision']
 def _stage(self,name):pass  # Fault-injection seam; no side effects in production.
 def save(self,state,*,expected_revision):
  if type(expected_revision) is not int or expected_revision<0:raise ValueError('Invalid expected revision')
  payload=state.snapshot()
  restore(payload)  # Recompute invariants even if trusted caller mutated attributes.
  path=self.path(state.task_id)
  lockfd=os.open(str(path)+'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  temp=None;replaced=False
  try:
   if not stat.S_ISREG(os.fstat(lockfd).st_mode):raise ValueError('Lock must be a regular file')
   deadline=time.monotonic()+self.lock_timeout
   while True:
    try:fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
    except BlockingIOError:
     if time.monotonic()>=deadline:raise TimeoutError('Checkpoint writer lock timed out')
     time.sleep(.01)
   try:_,current=self.load(state.task_id)
   except FileNotFoundError:current=0
   if current!=expected_revision:raise RevisionConflict('Checkpoint changed; reload before writing')
   body={'version':1,'revision':current+1,'payload':payload}
   raw=canonical({**body,'sha256':hashlib.sha256(canonical(body)).hexdigest()})
   if len(raw)>MAX_BYTES:raise ValueError('Checkpoint too large')
   fd,temp=tempfile.mkstemp(prefix='.checkpoint-',suffix='.tmp',dir=self.directory)
   with os.fdopen(fd,'wb') as stream:
    stream.write(raw);stream.flush();os.fsync(stream.fileno())
   self._stage('temp_synced')
   os.replace(temp,path);replaced=True
   self._stage('replaced')
   directory_fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
   try:os.fsync(directory_fd)
   finally:os.close(directory_fd)
   return current+1
  except Exception as error:
   if replaced:raise CommitUncertain('Rename completed but durability acknowledgement failed; reload and reconcile before retry') from error
   raise
  finally:
   if temp is not None and os.path.exists(temp):os.unlink(temp)
   os.close(lockfd)
