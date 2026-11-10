"""Durable monotonic reservation under a cooperative process lock.

A failed action consumes its revision; never silently retry an uncertain action.
"""
import fcntl,json,os,tempfile
from pathlib import Path
from contextlib import contextmanager
def save(path,value):
 fd,name=tempfile.mkstemp(dir=path.parent)
 with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
 os.replace(name,path)
 fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
class RevisionGate:
 def __init__(self,root):
  self.root=Path(root);self.root.mkdir(mode=0o700,exist_ok=True)
  if self.root.resolve()!=self.root or self.root.stat().st_uid!=os.getuid() or self.root.stat().st_mode&0o777!=0o700:raise ValueError('private root required')
 @contextmanager
 def reserve(self,expected):
  with (self.root/'lock').open('a') as f:
   fcntl.flock(f,fcntl.LOCK_EX);p=self.root/'revision.json'
   revision=json.loads(p.read_text()) if p.exists() else 0
   if type(expected)!=int or expected!=revision:raise ValueError('stale revision at action boundary')
   save(p,revision+1)
   yield revision+1
