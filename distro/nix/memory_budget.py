"""Conservative observation of host and visible cgroup memory; no limit changes."""
from pathlib import Path
import time
def read_bound(path,limit):
 with Path(path).open() as stream:value=stream.read(limit+1)
 if len(value)>limit:raise ValueError('memory input too large')
 return value
def observe(meminfo=Path('/proc/meminfo'),cgroup=Path('/sys/fs/cgroup')):
 available=next(int(line.split()[1])*1024 for line in read_bound(meminfo,65536).splitlines() if line.startswith('MemAvailable:'))
 limit=read_bound(Path(cgroup,'memory.max'),64).strip();current=int(read_bound(Path(cgroup,'memory.current'),64).strip())
 if available<0 or current<0 or (limit!='max' and (not limit.isdecimal() or int(limit)<0)):raise ValueError('invalid memory observation')
 remaining=None if limit=='max' else max(0,int(limit)-current)
 return {'sampled_monotonic_ns':time.monotonic_ns(),'host_available_bytes':available,'visible_cgroup_limit_bytes':None if limit=='max' else int(limit),'visible_cgroup_current_bytes':current,'visible_cgroup_remaining_bytes':remaining,'observed_headroom_bytes':available if remaining is None else min(available,remaining),'scope':'visible host/cgroup snapshot only; no reclaim or hidden-ancestor guarantee'}
def admit(memory_mib,reserve_mib=1024,observation=None):
 if type(memory_mib) is not int or not 256<=memory_mib<=10240 or type(reserve_mib) is not int or reserve_mib<512:raise ValueError('bounded guest and reserve required')
 observation=observe() if observation is None else observation
 required=(memory_mib+reserve_mib)*1024**2
 if observation['observed_headroom_bytes']<required:raise ValueError('insufficient observed host/cgroup headroom')
 return {**observation,'guest_memory_mib':memory_mib,'reserve_mib':reserve_mib,'required_headroom_bytes':required,'admitted':True}
