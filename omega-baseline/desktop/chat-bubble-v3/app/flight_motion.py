"""Slow bounded gliding with soft turns and no frame-count-dependent movement."""
import math
class FlightMotion:
 def __init__(self):
  self.x=0.;self.y=0.;self.direction=-1;self.crawl=False;self.paused=False
  self.vx=0.;self.base_y=0.;self.phase=0.
 def bound(self,width,height):
  self.x=max(0,min(self.x,max(0,width-192)))
  self.y=max(0,min(self.y,max(0,height-208)))
  self.base_y=max(0,min(self.base_y,max(0,height-208)))
 def drag(self,dx,dy,width,height):
  self.x+=dx;self.y+=dy;self.base_y=self.y;self.phase=0.;self.vx=0.;self.bound(width,height)
 def step(self,dt,width,height):
  self.bound(width,height)
  if not self.crawl or self.paused or not math.isfinite(dt):return
  remaining=max(0,min(dt,.1));limit=max(0,width-192);margin=min(28,limit/4)
  while remaining>0:
   step=min(remaining,1/120);remaining-=step
   distance=(limit-margin-self.x) if self.direction>0 else (self.x-margin)
   if distance<3:self.direction*=-1
   distance=(limit-margin-self.x) if self.direction>0 else (self.x-margin)
   desired=self.direction*min(48,math.sqrt(2*65*max(0,distance)))
   self.vx+=max(-65*step,min(65*step,desired-self.vx))
   self.x+=self.vx*step
   self.phase+=step*.72
  amplitude=min(4,max(0,self.base_y),max(0,height-208-self.base_y))
  self.y=self.base_y+amplitude*math.sin(self.phase)
  self.bound(width,height)
