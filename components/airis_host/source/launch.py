"""Bounded local Python launch; parent-death binding survives exec."""
import os
from pathlib import Path
import resource
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nars_hyperon/source'))
from parent_guard import bind_parent
if len(sys.argv)!=2:raise ValueError('Expected trusted parent PID')
bind_parent(int(sys.argv[1]))
for name,value in ((resource.RLIMIT_CPU,10),(resource.RLIMIT_AS,512*1024**2),
    (resource.RLIMIT_FSIZE,256*1024),(resource.RLIMIT_NOFILE,64),
    (resource.RLIMIT_NPROC,1),(resource.RLIMIT_CORE,0)):
    resource.setrlimit(name,(value,value))
os.execv(sys.executable,[sys.executable,'-I','-S','-B',str(Path(__file__).with_name('worker.py'))])
