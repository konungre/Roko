"""Private cooperative SQLite snapshot checkpoint; no package/execution authority."""
import hashlib,json,os,sqlite3,stat,threading
from pathlib import Path
from package_planning_v2 import SnapshotOnly
class AwarenessStore:
 def __init__(self,directory):
  self.root=Path(directory);self.root.mkdir(mode=0o700,exist_ok=True)
  info=self.root.lstat()
  if self.root.resolve()!=self.root or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('owned private canonical checkpoint directory required')
  path=self.root/'observations.sqlite'
  fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
  try:
   info=os.fstat(fd)
   if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:raise ValueError('private single-link checkpoint required')
  finally:os.close(fd)
  self.lock=threading.RLock();self.db=sqlite3.connect(path,isolation_level=None,timeout=2,check_same_thread=False)
  self.db.execute('PRAGMA synchronous=FULL')
  self.db.execute('CREATE TABLE IF NOT EXISTS observations(backend TEXT PRIMARY KEY, version INTEGER, payload TEXT, digest TEXT)')
 def _read(self,backend):
  row=self.db.execute('SELECT version,payload,digest FROM observations WHERE backend=?',(backend,)).fetchone()
  if row is None:return {'version':0,'snapshot':None}
  version,raw,expected=row
  if type(version)!=int or version<1 or len(raw.encode())>1024*1024 or hashlib.sha256(str(version).encode()+b'\0'+raw.encode()).hexdigest()!=expected:raise ValueError('corrupt checkpoint')
  data=json.loads(raw)
  if data['source']!=backend:raise ValueError('checkpoint backend mismatch')
  snapshot=SnapshotOnly(raw).observe()
  return {'version':version,'snapshot':snapshot}
 def load(self,backend):
  with self.lock:return self._read(backend)
 def save(self,backend,snapshot,expected_version):
  raw=json.dumps({'source':backend,'packages':snapshot.packages,'revision':snapshot.revision},sort_keys=True,separators=(',',':'))
  SnapshotOnly(raw)
  with self.lock:
   self.db.execute('BEGIN IMMEDIATE')
   try:
    current=self._read(backend)
    if type(expected_version)!=int or current['version']!=expected_version:raise ValueError('stale checkpoint publisher')
    version=expected_version+1
    self.db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?)',(backend,version,raw,hashlib.sha256(str(version).encode()+b'\0'+raw.encode()).hexdigest()))
    self.db.execute('COMMIT');return version
   except BaseException:self.db.execute('ROLLBACK');raise
 def close(self):
  with self.lock:self.db.close()
