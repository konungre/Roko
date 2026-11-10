"""Windowless startup helpers; companion UI opens only after a character click."""
import fcntl,os,stat
from pathlib import Path

def initial_position(width,height):
 return max(0,width-220),max(0,height-240)

def acquire_instance(directory):
 directory=Path(directory)
 directory.mkdir(mode=0o700,parents=True,exist_ok=True)
 info=directory.lstat()
 if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
  raise ValueError('Companion runtime directory must be private and owned by this user')
 fd=os.open(directory/'instance.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 info=os.fstat(fd)
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():os.close(fd);raise ValueError('Invalid companion lock')
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:os.close(fd);return None
 return fd
