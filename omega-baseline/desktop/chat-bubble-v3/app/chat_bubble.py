"""Transient character-anchored Wayland bubble. Backend supplied explicitly."""
from conversation_state import ConversationState
import threading

def placement(pet, canvas, preferred=(400,340)):
    x,y,w,h=pet; cw,ch=canvas
    # Even very small outputs must never receive an off-screen bubble.
    cw,ch=max(1,int(cw)),max(1,int(ch))
    margin=min(12,max(0,(min(cw,ch)-1)//2))
    bw=min(preferred[0],cw-2*margin);bh=min(preferred[1],ch-2*margin)
    above=y-bh-12>=margin
    bx=max(margin,min(cw-bw-margin,x+w/2-bw/2))
    by=y-bh-12 if above else y+h+12
    by=max(margin,min(ch-bh-margin,by))
    return tuple(map(int,(bx,by,bw,bh))),above

class ChatBubble:
    def __init__(self,Gtk,Gdk,GLib,Layer,geometry,submit=None,monitor=None,quit_callback=None,reset=None):
        self.Gtk,self.Gdk,self.GLib=Gtk,Gdk,GLib
        self.geometry,self.submit=geometry,submit
        self.monitor=monitor
        self.reset=reset;self.resetting=False
        self.state=ConversationState()
        self.window=Gtk.Window();self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True);self.window.set_resizable(False)
        self.window.set_app_paintable(True)
        visual=self.window.get_screen().get_rgba_visual()
        if visual:self.window.set_visual(visual)
        if Layer is None:raise RuntimeError('Chat bubble requires Wayland layer-shell')
        self.Layer=Layer;Layer.init_for_window(self.window)
        Layer.set_namespace(self.window,'roko-chat-bubble')
        Layer.set_layer(self.window,Layer.Layer.OVERLAY)
        Layer.set_exclusive_zone(self.window,0)
        Layer.set_keyboard_mode(self.window,Layer.KeyboardMode.ON_DEMAND)
        Layer.set_anchor(self.window,Layer.Edge.TOP,True);Layer.set_anchor(self.window,Layer.Edge.LEFT,True)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);box.set_border_width(14)
        box.set_name('roko-chat-bubble');self.window.add(box)
        header=Gtk.Box(spacing=8);header.pack_start(Gtk.Label(label='Roko'),True,True,0)
        close=Gtk.Button(label='×');close.connect('clicked',lambda _:self.hide());header.pack_end(close,False,False,0);box.pack_start(header,False,False,0)
        if quit_callback:
            quit_button=Gtk.Button(label='Quit')
            quit_button.connect('clicked',lambda _:quit_callback())
            header.pack_end(quit_button,False,False,0)
        self.reply=Gtk.Label(label='Talk to me.');self.reply.set_line_wrap(True);self.reply.set_xalign(0)
        self.reply.set_max_width_chars(44)
        self.reply.set_selectable(True)
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.add(self.reply);box.pack_start(scroll,True,True,0)
        self.reply.set_yalign(0)
        def reveal_latest(*_):
            adjustment=scroll.get_vadjustment()
            adjustment.set_value(max(0,adjustment.get_upper()-adjustment.get_page_size()))
        self.reply.connect('size-allocate',reveal_latest)
        self.entry=Gtk.Entry();self.entry.set_max_length(4000);self.entry.set_placeholder_text('Say something…');self.entry.connect('activate',self.send)
        composer=Gtk.Box(spacing=8)
        composer.pack_start(self.entry,True,True,0)
        send_button=Gtk.Button(label='Send');send_button.connect('clicked',self.send)
        composer.pack_end(send_button,False,False,0)
        box.pack_start(composer,False,False,0)
        if reset:
            new=Gtk.Button(label='New conversation');new.connect('clicked',self.new_conversation)
            box.pack_start(new,False,False,0)
        self.status=Gtk.Label(label='');self.status.set_line_wrap(True);box.pack_start(self.status,False,False,0)

        self.window.connect('delete-event',lambda *_:(self.hide() or True))
        self.window.connect('key-press-event',self.key)
        css=Gtk.CssProvider();css.load_from_data(b'''
        #roko-chat-bubble { background: #102a27; color: #f6efd4;
          border: 1px solid #b9a86a; border-radius: 22px; padding: 14px; }
        #roko-chat-bubble label { color: #f6efd4; }
        #roko-chat-bubble button { background-image: none; background-color: #25413a;
          color: #f6efd4; border: 1px solid #52634b; border-radius: 9px; box-shadow: none; }
        #roko-chat-bubble button:hover { background-color: #35594b; border-color: #b9a86a; }
        #roko-chat-bubble entry { background: #0a1c1b; color: #f6efd4;
          border: 1px solid #52634b; border-radius: 9px; box-shadow: none; }
        #roko-chat-bubble entry:focus { border-color: #dfc679; }
        ''')
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    def key(self,_w,event):
        if event.keyval==self.Gdk.KEY_Escape:self.hide();return True
        if event.keyval in (self.Gdk.KEY_Return,self.Gdk.KEY_KP_Enter) and self.entry.has_focus():
            self.send(self.entry);return True
        return False
    def position(self):
        if self.monitor:
            monitor=self.monitor()
            if monitor is not None:self.Layer.set_monitor(self.window,monitor)
        rect,_=placement(*self.geometry());x,y,w,h=rect
        self.window.set_default_size(w,h);self.window.resize(w,h)
        self.Layer.set_margin(self.window,self.Layer.Edge.LEFT,x);self.Layer.set_margin(self.window,self.Layer.Edge.TOP,y)
    def show(self):
        self.position();self.window.show_all();self.entry.grab_focus()
    def hide(self):
        self.state.stop()
        self.entry.set_sensitive(True)
        self.status.set_text('')
        self.render_transcript()
        self.window.hide()
    def close(self):
        self.state.stop(close=True)
        self.window.destroy()
    def render_transcript(self):
        self.reply.set_text('\n\n'.join(who + ': ' + text for who,text in self.state.turns[-40:]) or 'Talk to me.')
    def new_conversation(self,_button):
        if self.state.pending or self.state.closed or self.resetting:return
        self.resetting=True;self.entry.set_sensitive(False)
        self.status.set_text('Starting a new conversation…')
        def work():
            error=None
            try:self.reset()
            except Exception as exc:error=str(exc)
            def update():
                self.resetting=False
                if self.state.closed:return False
                self.entry.set_sensitive(True)
                if error:self.status.set_text(error)
                else:
                    self.state=ConversationState();self.status.set_text('');self.render_transcript()
                return False
            self.GLib.idle_add(update)
        threading.Thread(target=work,name='roko-conversation-reset',daemon=False).start()
    def send(self,_entry):
        text=self.entry.get_text().strip()
        if not text or self.state.pending or self.state.closed or self.resetting:return
        if self.submit is None:
            self.status.set_text('The Omega conversation service is not connected yet.');return
        token=self.state.begin(text)
        self.entry.set_sensitive(False);self.entry.set_text('');self.status.set_text('Thinking…')
        self.render_transcript()
        def done(answer,error=None):
            def update():
                if self.state.finish(token,answer,error):
                    self.entry.set_sensitive(True)
                    self.status.set_text('')
                    self.render_transcript()
                    self.entry.grab_focus()
                return False
            self.GLib.idle_add(update)
        try:
            self.state.attach_cancel(token,self.submit(text,done))
        except Exception as exc:
            done(None,str(exc))
