"""Elapsed-time pose blending; original sprite pixels are never redrawn."""
import math

class PoseBlend:
 def __init__(self,duration=.28):
  self.duration=duration;self.source={};self.target=None;self.elapsed=duration
 def weights(self):
  if self.target is None:return {}
  t=min(1,max(0,self.elapsed/self.duration));t=t*t*(3-2*t)
  result={key:value*(1-t) for key,value in self.source.items()}
  result[self.target]=result.get(self.target,0)+t
  return {key:value for key,value in result.items() if value>1e-9}
 def set_target(self,key,instant=False):
  if key==self.target:return
  self.source=self.weights();self.target=key
  if instant or not self.source:self.source={key:1};self.elapsed=self.duration
  else:self.elapsed=0.
 def step(self,dt,paused=False):
  if not paused and math.isfinite(dt):self.elapsed=min(self.duration,self.elapsed+max(0,min(dt,.1)))

def pose_key(character,busy,state,flying,perching,now):
 if character.resting:return 3
 if flying or perching:return 'flight'
 if now<character.response_until:return character.response
 if busy or state in ('thinking','review','waiting'):return 4
 if state=='complete':return 2
 return 0

class RenderGate:
 """Return only changed sprite bounds; never ask GTK to redraw the whole desktop."""
 def __init__(self):self.last=None
 def update(self,visible,x,y,weights):
  current=(bool(visible),float(x),float(y),tuple(sorted(((str(k),round(v,6)) for k,v in weights.items()))))
  previous=self.last;self.last=current
  if previous==current:return None
  bounds=[]
  for item in (previous,current):
   if item and item[0]:bounds.append((math.floor(item[1])-2,math.floor(item[2])-2,math.ceil(item[1])+194,math.ceil(item[2])+210))
  if not bounds:return None
  left=min(b[0] for b in bounds);top=min(b[1] for b in bounds)
  return left,top,max(b[2] for b in bounds)-left,max(b[3] for b in bounds)-top
