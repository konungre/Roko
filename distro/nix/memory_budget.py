"""Conservative observation of host and visible cgroup memory; no limit changes."""
from pathlib import Path
import time,os,re,stat
def read_bound(path,limit):
 fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
 try:
  if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('regular memory input required')
  value=os.read(fd,limit+1)
 finally:os.close(fd)
 if len(value)>limit:raise ValueError('memory input too large')
 return value.decode('ascii')
def observe(meminfo=Path('/proc/meminfo'),cgroup=Path('/sys/fs/cgroup')):
 rows=[line for line in read_bound(meminfo,65536).splitlines() if line.startswith('MemAvailable:')]
 if len(rows)!=1 or not re.fullmatch(r'MemAvailable:[ \t]+[0-9]+[ \t]+kB[ \t]*',rows[0]):raise ValueError('one valid MemAvailable value required')
 available=int(rows[0].split()[1])*1024
 limit=read_bound(Path(cgroup,'memory.max'),64).strip();raw_current=read_bound(Path(cgroup,'memory.current'),64).strip()
 if not re.fullmatch('[0-9]+',raw_current) or (limit!='max' and not re.fullmatch('[0-9]+',limit)):raise ValueError('invalid memory observation')
 current=int(raw_current)
 remaining=None if limit=='max' else max(0,int(limit)-current)
 return {'sampled_monotonic_ns':time.monotonic_ns(),'host_available_bytes':available,'visible_cgroup_limit_bytes':None if limit=='max' else int(limit),'visible_cgroup_current_bytes':current,'visible_cgroup_remaining_bytes':remaining,'observed_headroom_bytes':available if remaining is None else min(available,remaining),'scope':'visible host/cgroup snapshot only; no reclaim or hidden-ancestor guarantee'}
def admit(memory_mib,reserve_mib=1024,observation=None):
 if type(memory_mib) is not int or not 256<=memory_mib<=10240 or type(reserve_mib) is not int or reserve_mib<512:raise ValueError('bounded guest and reserve required')
 observation=observe() if observation is None else observation
 required=(memory_mib+reserve_mib)*1024**2
 if observation['observed_headroom_bytes']<required:raise ValueError('insufficient observed host/cgroup headroom')
 return {**observation,'guest_memory_mib':memory_mib,'reserve_mib':reserve_mib,'required_headroom_bytes':required,'admitted':True}
