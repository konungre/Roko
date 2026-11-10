"""Unexecuted GTK adapter; caller must supply reviewed head_region output.
No imports/GUI work until construction. No automatic companion integration.
"""
class HeadTarget:
    def __init__(self,Gtk,Gdk,Layer,cairo,on_activate):
        self.cairo=cairo;self.on_activate=on_activate;self.rects=();self.armed=False
        self.window=Gtk.Window();self.window.set_decorated(False)
        self.window.set_app_paintable(True)
        visual=self.window.get_screen().get_rgba_visual()
        if visual is None:raise ValueError('RGBA unavailable')
        self.window.set_visual(visual);Layer.init_for_window(self.window)
        Layer.set_namespace(self.window,'roko-head-input-experimental')
        Layer.set_layer(self.window,Layer.Layer.TOP)
        Layer.set_keyboard_mode(self.window,Layer.KeyboardMode.NONE)
        Layer.set_exclusive_zone(self.window,0)
        for edge in (Layer.Edge.TOP,Layer.Edge.BOTTOM,Layer.Edge.LEFT,Layer.Edge.RIGHT):
            Layer.set_anchor(self.window,edge,True)
        self.canvas=Gtk.DrawingArea();self.window.add(self.canvas)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.canvas.connect('draw',self.draw)
        self.canvas.connect('button-press-event',self.press)
        self.canvas.connect('button-release-event',self.release)
        self.window.connect('realize',self.invalidate)
        for name in ('map-event','unmap-event','configure-event','grab-broken-event'):
            self.window.connect(name,self.invalidate)
        self.canvas.connect('size-allocate',self.invalidate)
        # Map with empty input first; then verify actual configured coordinate spaces
        # and apply. Never infer a mapped allocation before mapping.
    def draw(self,_widget,cr):
        cr.set_operator(self.cairo.OPERATOR_SOURCE);cr.set_source_rgba(0,0,0,0);cr.paint();return False
    def invalidate(self,*_):
        # Also called explicitly for pose/visibility/tracker/scene changes.
        self.clear();return False
    def clear(self):
        self.rects=();self.armed=False
        if self.window.get_window():self.window.get_window().input_shape_combine_region(self.cairo.Region(),0,0)
    def apply(self,rects,verified_allocation):
        self.clear()
        if not self.window.get_window() or not self.window.get_mapped():return False
        actual=(self.canvas.get_allocated_width(),self.canvas.get_allocated_height())
        if tuple(verified_allocation)!=actual:return False
        if type(rects) is not tuple or len(rects)>4096:return False
        for rect in rects:
            if type(rect) is not tuple or len(rect)!=4 or any(type(v) is not int for v in rect):return False
            x,y,w,h=rect
            if not (0<=x<x+w<=actual[0] and 0<=y<y+h<=actual[1]):return False
        r=self.cairo.Region()
        for rect in rects:r.union(self.cairo.RectangleInt(*rect))
        self.window.get_window().input_shape_combine_region(r,0,0);self.rects=rects
        return True
    def contains(self,x,y):return any(a<=x<a+w and b<=y<b+h for a,b,w,h in self.rects)
    def press(self,_widget,event):
        self.armed=event.button==1 and self.contains(event.x,event.y);return self.armed
    def release(self,_widget,event):
        activate=self.armed and event.button==1 and self.contains(event.x,event.y)
        self.armed=False
        if activate:self.clear();self.on_activate(event.x,event.y)
        return activate
    def close(self):self.clear();self.window.destroy()
