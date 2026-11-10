"""Pure geometry and visibility policies for the windowless Roko companion."""
from lifecycle import initial_position

class DefaultAnchor:
    """Follow final compositor allocations until the user chooses movement."""
    def __init__(self,enabled=True):
        self.enabled=enabled
        self.last_size=None
    def manual(self):
        self.enabled=False
    def allocate(self,width,height):
        size=(width,height)
        changed=size!=self.last_size
        self.last_size=size
        if self.enabled and changed and width>192 and height>208:
            return initial_position(width,height)
        return None

def interaction_size(width,height,preferred_width=540):
    """Leave room for COSMIC decoration/panel/dock; content scrolls to fit."""
    if width<=0 or height<=0:
        raise ValueError('Monitor work area must be positive')
    return min(preferred_width,max(1,width-48)),min(560,max(1,height-176))

def avatar_visible(perching,has_target,panel_visible,task_visible):
    return not (panel_visible or task_visible) and (not perching or has_target)
