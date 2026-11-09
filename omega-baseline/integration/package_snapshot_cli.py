#!/usr/bin/env python3
"""Explicit v2 read-only planning CLI; not a replacement for legacy apply/state."""
import argparse,os,stat,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters'))
def read_text(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_size>1024*1024:raise ValueError('bounded regular input required')
  raw=f.read(1024*1024+1)
  if len(raw)>1024*1024:raise ValueError('input grew beyond bound')
  return raw.decode()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--planner',required=True,choices=['successor-v2']);p.add_argument('--desired',required=True);p.add_argument('--snapshot',required=True);a=p.parse_args()
 if os.geteuid()==0:raise ValueError('run as an unprivileged operator')
 from package_planning_v2 import plan_source
 import json
 print(json.dumps(plan_source(read_text(a.desired),read_text(a.snapshot)),sort_keys=True))
if __name__=='__main__':
 try:main()
 except (ValueError,OSError) as e:print('read-only planning failed: '+str(e),file=sys.stderr);raise SystemExit(1)
