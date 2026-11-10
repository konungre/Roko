"""Narrow JSON intent boundary for already-built private Nix profile outputs.

New implementation; no import from the unlicensed historical prototype.
No expression evaluation, downloads, system activation or embedded authorization.
"""
import hashlib,json,re
from pathlib import Path
from facts import digest

def desired(document,store_root,lock_bytes):
 if not isinstance(document,dict) or set(document)!={'schema','backend','source_lock_sha256','packages'}:raise ValueError('intent fields')
 if document['schema']!='roko-private-intent-v1' or document['backend']!='nix':raise ValueError('intent version/backend')
 if document['source_lock_sha256']!=hashlib.sha256(lock_bytes).hexdigest():raise ValueError('source lock mismatch')
 packages=document['packages']
 if not isinstance(packages,dict) or not 1<=len(packages)<=128:raise ValueError('bounded nonempty package set')
 root=Path(store_root)
 if not root.is_absolute() or root!=root.resolve():raise ValueError('canonical store root')
 for name,path in packages.items():
  if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}',name):raise ValueError('package name')
  if not isinstance(path,str) or Path(path).parent!=root or not re.fullmatch('[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9._+-]+',Path(path).name):raise ValueError('exact store output required')
 if len(set(packages.values()))!=len(packages):raise ValueError('output aliases unsupported')
 return dict(sorted(packages.items()))

class Reconciler:
 def __init__(self,profiles,store_root):self.profiles=profiles;self.store_root=store_root
 def prepare(self,document,lock_bytes):
  packages=desired(document,self.store_root,lock_bytes)
  # These receipts establish local closure availability, not source audit/trust.
  closure={p:self.profiles.run('path-info','--recursive',p) for p in packages.values()}
  body={'schema':'roko-private-plan-v1','profile_root':str(self.profiles.root),'expected':self.profiles.current(),'desired':packages,'source_lock_sha256':document['source_lock_sha256'],'closure':closure}
  return {**body,'digest':digest(body)}
 def apply(self,plan,lock_bytes,review):
  # Freeze caller-owned input before any potentially re-entrant review callback.
  frozen=json.loads(json.dumps(plan));identity=frozen.pop('digest',None)
  if set(frozen)!={'schema','profile_root','expected','desired','source_lock_sha256','closure'} or digest(frozen)!=identity:raise ValueError('plan integrity')
  if frozen['schema']!='roko-private-plan-v1' or frozen['profile_root']!=str(self.profiles.root):raise ValueError('plan scope')
  packages=desired({'schema':'roko-private-intent-v1','backend':'nix','packages':frozen['desired'],'source_lock_sha256':frozen['source_lock_sha256']},self.store_root,lock_bytes)
  # Checksums are not authorization. Only this trusted callback grants review.
  if review(json.loads(json.dumps({**frozen,'digest':identity}))) is not True:raise PermissionError('review required')
  return self.profiles.switch(packages,frozen['expected'],True)
