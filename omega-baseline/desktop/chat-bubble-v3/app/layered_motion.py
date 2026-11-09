"""Real geometry routing; no synthetic occlusion or arbitrary per-window z-order."""
from corner_motion import CornerFollow

class LayeredFollow(CornerFollow):
    def __init__(self):
        super().__init__();self.route=None;self.phase='hidden';self.layer='bottom';self.corner=None
    def clear(self,reason):
        super().clear(reason);self.route=None;self.phase='hidden';self.layer='bottom';self.corner=None
    def update(self,rect,observer,canvas,*,fullscreen=False,maximized=False):
        if not super().update(rect,observer,canvas,fullscreen=fullscreen,maximized=maximized):return False
        corner=self.target;x,y,w,h=rect
        # Switch only when the ENTIRE sprite is outside the active rectangle.
        # Other ordinary windows may still overlap this waypoint.
        if x>=200:waypoint=(x-200,y-65)
        elif y>=216:waypoint=(x-60,y-216)
        else:
            self.clear('No outside-window waypoint fits for layered flight');return False
        route=(tuple(rect),tuple(canvas))
        if route!=self.route:
            # Never promote a previously occluded body on geometry changes.
            outside=(self.x+192<=x or self.x>=x+w or self.y+208<=y or self.y>=y+h)
            front_allowed=self.route is None and outside
            self.route=route;self.phase='approach' if front_allowed else 'settle'
            self.layer='top' if front_allowed else 'bottom';self.arrived=False
        self.corner=corner
        self.target=waypoint if self.phase=='approach' else corner
        self.arrived=self.phase=='perched'
        return True
    def step(self,dt):
        super().step(dt)
        if self.arrived and self.phase=='approach':
            self.phase='settle';self.layer='bottom';self.target=self.corner;self.arrived=False
        elif self.arrived and self.phase=='settle':self.phase='perched'

class LayerRequests:
    """One cache for ALL layer requests; not compositor acknowledgement."""
    def __init__(self,setter):self.setter=setter;self.requested=None
    def set(self,layer):
        if layer not in ('top','bottom'):raise ValueError('Invalid layer')
        if self.requested!=layer:
            self.setter(layer)
            self.requested=layer
