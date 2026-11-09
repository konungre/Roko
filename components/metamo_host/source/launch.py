"""Resource limits and caller lifetime binding before exec of local SWI."""
import os
from pathlib import Path
import resource
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nars_hyperon/source'))
from parent_guard import bind_parent

if len(sys.argv)!=3:raise ValueError('Fixed parent and SWI arguments required')
bind_parent(int(sys.argv[1]))
for name,value in ((resource.RLIMIT_CPU,5),(resource.RLIMIT_AS,512*1024**2),
    (resource.RLIMIT_FSIZE,128*1024),(resource.RLIMIT_NOFILE,64),
    (resource.RLIMIT_NPROC,1),(resource.RLIMIT_CORE,0)):
    resource.setrlimit(name,(value,value))
worker=Path(__file__).with_name('worker.pl')
os.execv(sys.argv[2],[sys.argv[2],'--stack-limit=64m','-q','-f','none','--no-packs',
                    '-s',str(worker),'--','silent'])
