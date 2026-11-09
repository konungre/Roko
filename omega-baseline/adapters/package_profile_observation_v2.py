"""Opt-in native Nix profile observation. No activation or path rewriting.

Command prefix/environment/profile are trusted controller configuration. This
observer supplies package facts, not installed/running OS health or authority.
"""
import hashlib,json,os,subprocess
from pathlib import Path
from types import SimpleNamespace
class ReadOnlyProfile:
 def __init__(self,command,profile,env):
  self.command=list(command);self.profile=Path(profile);self.env=dict(env);self.calls=0;self.last_receipt=None
  if not self.command or not self.profile.is_absolute():raise ValueError('explicit command and absolute profile required')
  self.identity='nix-profile-observation-v2:'+str(self.profile)
 def _target(self):
  if not self.profile.is_symlink():raise ValueError('existing profile symlink required')
  target=self.profile.resolve(strict=True)
  return {'link':os.readlink(self.profile),'resolved':str(target),'manifest_sha256':hashlib.sha256((target/'manifest.json').read_bytes()).hexdigest()}
 def observe(self):
  self.calls+=1;before=self._target()
  result=subprocess.run(self.command+['profile','list','--profile',str(self.profile),'--json'],env=self.env,capture_output=True,text=True,timeout=20)
  if result.returncode:raise ValueError('native profile observation failed: '+result.stderr[:4096])
  if len(result.stdout.encode())>1024*1024:raise ValueError('profile observation too large')
  def unique(pairs):
   obj={}
   for key,value in pairs:
    if key in obj:raise ValueError('duplicate native profile field')
    obj[key]=value
   return obj
  native=json.loads(result.stdout,object_pairs_hook=unique)
  if not isinstance(native,dict):raise ValueError('native profile object required')
  if type(native.get('version')) is not int or native['version']!=3 or not isinstance(native.get('elements'),dict):raise ValueError('unsupported native profile schema')
  packages={}
  for name,element in native['elements'].items():
   if not isinstance(element,dict) or type(element.get('active',True)) is not bool:raise ValueError('invalid native element')
   if not element.get('active',True):continue
   paths=element.get('storePaths')
   if not isinstance(paths,list) or len(paths)!=1 or not isinstance(paths[0],str):raise ValueError('single output per package required')
   packages[name]=paths[0]
  after=self._target()
  if before!=after:raise ValueError('profile changed during observation')
  raw_digest=hashlib.sha256(result.stdout.encode()).hexdigest()
  receipt={'schema':'roko.native-profile-observation.v2','profile':str(self.profile),'target':before,'native':native,'native_stdout_sha256':raw_digest,'source':self.identity,'scope':'point-in-time-read-only-profile','authorizes_actions':False}
  revision=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  receipt['revision']=revision;self.last_receipt=receipt
  return SimpleNamespace(packages=packages,revision=revision)
