"""Single-owner fixture decision freshness, NOT authentication or a restart API."""
from dataclasses import dataclass
import threading,uuid
@dataclass(frozen=True)
class Choice:
 action:str
 epoch:str
 revision:int
class FixtureChoices:
 def __init__(self):self.epoch=uuid.uuid4().hex;self.revision=0;self.lock=threading.RLock()
 def choose(self,action):
  if action not in ('restart','keep-stopped'):raise ValueError('explicit fixture choice required')
  with self.lock:return Choice(action,self.epoch,self.revision)
 def changed(self,new_desktop=False):
  with self.lock:
   self.revision+=1
   if new_desktop:self.epoch=uuid.uuid4().hex
 def apply(self,choice,start):
  with self.lock:
   if not isinstance(choice,Choice) or type(choice.revision) is not int or not isinstance(choice.epoch,str) or choice.action not in ('restart','keep-stopped') or choice.epoch!=self.epoch or choice.revision!=self.revision:raise ValueError('stale or invalid fixture choice')
   self.revision+=1 # consume before callback; failed launch never revives a choice
   if choice.action=='keep-stopped':return None
   return start()
