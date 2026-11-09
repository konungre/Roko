"""Nix2.26 private-profile successor: prepare a complete profile, switch one pointer.

No host profile/system activation. Failed candidates are retained, never adopted.
"""
import fcntl,json,os,re,subprocess,uuid
from pathlib import Path
class Profiles:
 def __init__(self,root,nix,store,env):
  self.root=Path(root);self.nix=nix;self.store=store;self.env=env
  self.root.mkdir(mode=0o700,exist_ok=True)
  info=self.root.lstat()
  if self.root.resolve()!=self.root or info.st_uid!=os.getuid() or info.st_mode&0o777!=0o700:raise ValueError('private canonical root required')
 def run(self,*args):
  r=subprocess.run([self.nix,'--extra-experimental-features','nix-command flakes','--store',self.store,'--offline',*args],env=self.env,capture_output=True,text=True,timeout=120)
  if r.returncode:raise RuntimeError(r.stderr)
  return r.stdout
 def current(self):
  p=self.root/'active'
  if os.path.lexists(p) and not p.is_symlink():raise ValueError('foreign active pointer')
  return os.readlink(p) if p.is_symlink() else None
 def switch(self,packages,expected,review):
  if review is not True:raise PermissionError('external review required')
  if not packages:raise ValueError('empty profile not supported yet')
  if any(not re.fullmatch('[a-z][a-z0-9-]{0,63}',n) or not Path(p).is_absolute() for n,p in packages.items()):raise ValueError('invalid packages')
  if len(set(packages.values()))!=len(packages):raise ValueError('ambiguous output aliases')
  with (self.root/'lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   if self.current()!=expected:raise ValueError('stale profile')
   for p in packages.values():self.run('path-info','--recursive',p)
   candidate=self.root/('generation-'+uuid.uuid4().hex);candidate.mkdir(mode=0o700)
   profile=candidate/'profile'
   self.run('profile','install','--profile',str(profile),*sorted(packages.values()))
   observed=json.loads(self.run('profile','list','--profile',str(profile),'--json'))
   paths=[p for e in observed['elements'].values() if e.get('active',True) for p in e['storePaths']]
   if sorted(paths)!=sorted(packages.values()):raise ValueError('candidate mismatch')
   receipt={'packages':packages,'native':observed,'previous':expected,'scope':'private-user-profile'}
   with (candidate/'receipt.json').open('x') as f:json.dump(receipt,f);f.flush();os.fsync(f.fileno())
   fd=os.open(candidate,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
   if self.current()!=expected:raise ValueError('concurrent drift')
   temporary=self.root/('pointer-'+uuid.uuid4().hex)
   os.symlink(str(profile),temporary);os.replace(temporary,self.root/'active')
   fd=os.open(self.root,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
   return {'before':expected,'after':self.current(),'receipt':receipt}
 def rollback(self,target,expected,review):
  if review is not True:raise PermissionError('external review required')
  target=Path(target)
  if target.name!='profile' or target.parent.parent!=self.root or not re.fullmatch('generation-[0-9a-f]{32}',target.parent.name):raise ValueError('foreign generation')
  if target.parent.is_symlink() or not target.exists():raise ValueError('missing retained generation')
  with (self.root/'lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   if self.current()!=expected:raise ValueError('stale profile')
   receipt=json.loads((target.parent/'receipt.json').read_text())
   observed=json.loads(self.run('profile','list','--profile',str(target),'--json'))
   if observed!=receipt['native']:raise ValueError('retained profile changed')
   temporary=self.root/('pointer-'+uuid.uuid4().hex)
   os.symlink(str(target),temporary);os.replace(temporary,self.root/'active')
   fd=os.open(self.root,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
   return {'before':expected,'after':self.current(),'native':observed,'scope':'private-user-profile-rollback'}
