#!/usr/bin/env python3
"""Verify the previously recorded extracted workspace runtime, without executing it."""
import hashlib,json,os,stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
 lock=json.loads((ROOT/'boot/tooling-files.lock.json').read_text());errors=[]
 for name,record in lock['files'].items():
  path=ROOT/'boot/tooling/root'/name
  if record['kind']=='symlink':
   if not path.is_symlink() or os.readlink(path)!=record['target']:errors.append(name)
  elif not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256'] or stat.S_IMODE(path.stat().st_mode)!=record['mode']:errors.append(name)
 return {'checked_entries':len(lock['files']),'errors':errors,'success':not errors}
if __name__=='__main__':
 result=verify();print(json.dumps(result,indent=2));raise SystemExit(not result['success'])
