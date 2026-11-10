"""Geometry-only corner approach; compositor, never client, performs occlusion."""
import math

class CornerFollow:
    def __init__(self):
        self.target=None
        self.reason='Waiting for an actual active-window report'
        self.x=0.0;self.y=0.0;self.direction=1
        self.arrived=False
        self.vx=0.0;self.vy=0.0
    def clear(self,reason):
        self.target=None;self.arrived=False;self.reason=reason;self.vx=0.;self.vy=0.
    def update(self,rect,observer,canvas,*,fullscreen=False,maximized=False):
        if observer!=canvas:
            self.clear('Observer and avatar coordinate spaces differ');return False
        if fullscreen or maximized:
            self.clear('No corner perch for fullscreen or maximized windows');return False
        if (len(rect)!=4 or any(type(v) is not int for v in rect)
                or any(type(v) is not int or v<=0 for v in canvas)):
            self.clear('Invalid geometry');return False
        x,y,w,h=rect;cw,ch=canvas
        if x<60 or y<65 or w<132 or h<143 or x+w>cw or y+h>ch:
            self.clear('Window corner is clipped, too close to an edge, or too small');return False
        tx,ty=x-60,y-65
        if tx+192>cw or ty+208>ch:
            self.clear('Character would not fit beside this corner');return False
        self.target=(tx,ty);self.reason='Following the actual active-window corner'
        self.arrived=math.hypot(tx-self.x,ty-self.y)<=0.5 and math.hypot(self.vx,self.vy)<4
        return True
    def step(self,dt):
        if self.target is None:return
        remaining=max(0,min(dt,0.1))
        while remaining>0:
            step=min(remaining,1/120);remaining-=step
            dx,dy=self.target[0]-self.x,self.target[1]-self.y
            distance=math.hypot(dx,dy)
            if distance<=0.5 and math.hypot(self.vx,self.vy)<4:
                self.x,self.y=self.target;self.vx=0.;self.vy=0.;self.arrived=True;return
            self.arrived=False
            ax,ay=16*dx-8*self.vx,16*dy-8*self.vy
            acceleration=math.hypot(ax,ay)
            if acceleration>140:ax*=140/acceleration;ay*=140/acceleration
            self.vx+=ax*step;self.vy+=ay*step
            speed=math.hypot(self.vx,self.vy)
            if speed>110:self.vx*=110/speed;self.vy*=110/speed
            if self.vx:self.direction=1 if self.vx>0 else -1
            self.x+=self.vx*step;self.y+=self.vy*step


def status_text(follow, *, enabled, paused=False, resting=False):
    """Derive visible UI wording from the same eligibility used for rendering."""
    if not enabled:
        return 'Corner following off · drag Roko or enable Glide around'
    if follow.target is None:
        return 'Hidden · ' + follow.reason
    if resting:
        return 'Resting · corner motion stopped'
    if paused:
        return 'Paused · corner motion stopped'
    if follow.arrived:
        return 'Perched · at the actual active-window corner'
    return 'Flying · toward the actual active-window corner'
