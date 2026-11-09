#!/usr/bin/env python3
"""Omega desktop avatar; transparent layer by default, click to converse."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import os
import subprocess
import signal
from chat_bubble import ChatBubble
from input_mask import opaque_intersection
from omega_transport import OmegaTransport
from corner_motion import CornerFollow, status_text
from layered_motion import LayeredFollow, LayerRequests
from flight_motion import FlightMotion
from animation import PoseBlend, pose_key, RenderGate
from lifecycle import acquire_instance
from ui_layout import DefaultAnchor, avatar_visible
from tracker_client import parse_report, MAX_LINE
from head_region import head_region
from gtk_target import HeadTarget
from sender_lease import SenderLease
from head_report import consume as consume_head_report
HEAD_TRACKER_SHA256="8eec35fc7a8bbe298ff8aab6c585b190acd66813b1ddf44bc5f33bd0bfa5aab9" # Offline-tested heartbeat; live GUI remains unqualified.
from character import Character, rectangle
from avatar_state import read_event
BASE = Path(__file__).resolve().parent

def verify_asset():
    manifest=json.loads((BASE/'manifest.json').read_text())
    asset=BASE/'assets/character.png'
    if hashlib.sha256(asset.read_bytes()).hexdigest()!=manifest['sha256']:
        raise ValueError('Roko artwork checksum mismatch')
    corner=BASE/'assets/corner.png'
    if hashlib.sha256(corner.read_bytes()).hexdigest()!=manifest['corner_sha256']:
        raise ValueError('Corner artwork checksum mismatch')
    return asset

def main(argv=None, *, conversation_submit=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experimental-single-window-head-input',action='store_true',help='Test-only: operator verifies no other windows/popups cover exposed head')
    p.add_argument('--check', action='store_true')
    p.add_argument('--overlay', action='store_true', default=True, help='Require Wayland layer-shell (default; no window fallback)')
    p.add_argument('--events',type=Path,help='Read a local Omega cosmetic-event file')
    p.add_argument('--layered-flight',action='store_true',help='Experimental genuine TOP approach then BOTTOM corner settle; requires --perch-active')
    p.add_argument('--perch-active',action='store_true',help='Use actual COSMIC active-window geometry and bottom-layer occlusion')
    p.add_argument('--tracker',type=Path,default=BASE/'tracker/roko-window-tracker')
    p.add_argument('--conversation-runner',type=Path,default=Path('/opt/roko/components/conversation/run.py'),help='Actual Omega JSON-lines runner; absolute path')
    p.add_argument('--conversation-python',type=Path,default=Path('/usr/bin/python3'))
    args=p.parse_args(argv)
    if not args.conversation_runner.is_absolute() or not args.conversation_python.is_absolute():
        p.error('Conversation runner and Python must be absolute paths')
    if args.experimental_single_window_head_input:
        if not (args.overlay and args.perch_active and args.layered_flight):p.error('Experimental head target requires overlay, perching and layered flight')
        if HEAD_TRACKER_SHA256 is None:p.error('Experimental heartbeat tracker is not bound')
        if hashlib.sha256(args.tracker.read_bytes()).hexdigest()!=HEAD_TRACKER_SHA256:p.error('Unverified heartbeat tracker')
    if args.layered_flight and not args.perch_active:p.error('--layered-flight requires --perch-active')
    if args.perch_active and not args.overlay:p.error('--perch-active requires --overlay')
    try: asset=verify_asset()
    except (ValueError,OSError,KeyError) as exc:
        print(exc,file=sys.stderr); return 1
    if args.check:
        print('Selected Roko character asset checksum verified; no display check.'); return 0
    runtime_base=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.local/state')))/'roko-companion'
    try:instance_fd=acquire_instance(runtime_base)
    except (OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr);return 2
    if instance_fd is None:
        print('Roko is already running. Click the basilisk to interact.');return 0
    try:
        import gi
        gi.require_version('Gtk','3.0')
        gi.require_foreign('cairo')
        from gi.repository import Gtk,Gdk,GdkPixbuf,GLib,Gio
        import cairo
    except (ImportError,ValueError):
        print('Requires system Python with python3-gi, python3-gi-cairo, python3-cairo and GTK 3.',file=sys.stderr); return 2
    GLib.set_prgname('roko-companion')
    ready,_=Gtk.init_check([])
    if not ready:
        print('No graphical session available.',file=sys.stderr); return 2
    Layer=None
    if args.overlay:
        try:
            gi.require_version('GtkLayerShell','0.1')
            from gi.repository import GtkLayerShell as Layer
            if not Layer.is_supported(): raise ValueError('Compositor lacks layer-shell support')
        except (ImportError,ValueError) as exc:
            print('Overlay unavailable: '+str(exc)+'. A Wayland layer-shell session is required.',file=sys.stderr); return 2
    css=Gtk.CssProvider();css.load_from_path(str(BASE/'theme.css'))
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    sheet=GdkPixbuf.Pixbuf.new_from_file(str(asset))
    if (sheet.get_width(),sheet.get_height())!=(768,416): return 1
    window=Gtk.Window(title='Roko · your AI companion')
    window.set_default_size(640,320)
    layers=LayerRequests(lambda value:Layer.set_layer(window,Layer.Layer.TOP if value=='top' else Layer.Layer.BOTTOM))
    if Layer:
        window.set_decorated(False)
        window.set_app_paintable(True)
        visual=window.get_screen().get_rgba_visual()
        if not visual:
            print('Transparent visual unavailable; overlay refused.',file=sys.stderr);return 2
        window.set_visual(visual)
        Layer.init_for_window(window)
        Layer.set_namespace(window,'roko-avatar')
        layers.set('bottom' if args.perch_active else 'top')
        Layer.set_keyboard_mode(window,Layer.KeyboardMode.NONE)
        Layer.set_exclusive_zone(window,0)
        for edge in (Layer.Edge.TOP,Layer.Edge.BOTTOM,Layer.Edge.LEFT,Layer.Edge.RIGHT):
            Layer.set_anchor(window,edge,True)
    canvas=Gtk.DrawingArea()
    canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
    window.add(canvas)
    corner_asset=BASE/'assets/corner.png'
    if hashlib.sha256(corner_asset.read_bytes()).hexdigest()!=json.loads((BASE/'manifest.json').read_text())['corner_sha256']:
        print('Corner artwork checksum mismatch',file=sys.stderr);return 1
    corner_pix=GdkPixbuf.Pixbuf.new_from_file(str(corner_asset))
    follow=LayeredFollow() if args.layered_flight else CornerFollow();last_report=[None];tracker_proc=[None];tracker_watch=[None];tracker_buffer=bytearray()
    head_target=[None];head_lease=SenderLease()
    character=Character()
    pose_blend=PoseBlend();pose_blend.set_target(0)
    render_gate=RenderGate()
    animation_clock=[time.monotonic()]
    label=Gtk.Label(label='Your local AI companion' if not args.events else 'Roko · awaiting state report')
    mood=Gtk.Label(label='A little company. A little curiosity. Ready when you are.')
    mood.set_line_wrap(True)
    motion=FlightMotion();motion.crawl=True; frame=[0]; state=['idle']; wave_until=[0.0];drag=[None];moved=[False]
    anchor=DefaultAnchor(enabled=not args.perch_active)
    perch=Gtk.CheckButton(label='Follow active window’s upper-left corner')
    perch.set_active(args.perch_active);perch.set_sensitive(bool(Layer))
    def perch_changed(widget):
        if head_target[0]:head_target[0].invalidate()
        if args.layered_flight:follow.clear('Waiting for an actual active-window report')
        if Layer:layers.set('bottom' if widget.get_active() else 'top')
        if widget.get_active():
            anchor.manual()
            follow.x,follow.y=motion.x,motion.y;follow.vx=0.;follow.vy=0.
        else:motion.base_y=motion.y
    perch.connect('toggled',perch_changed)
    perch_status=Gtk.Label(label='Real corner following: single output, floating windows only' if args.perch_active else 'Corner following requires --overlay --perch-active')
    perch_status.set_line_wrap(True)
    crawl=Gtk.CheckButton(label='Glide around');crawl.set_active(True)
    pause=Gtk.CheckButton(label='Pause animation and flight')
    def crawl_changed(widget):
        motion.crawl=widget.get_active()
        if motion.crawl:anchor.manual()
    crawl.connect('toggled',crawl_changed)
    pause.connect('toggled',lambda w:setattr(motion,'paused',w.get_active()))
    def care(action):
        if head_target[0]:head_target[0].invalidate()
        mood.set_text(character.care(action,now=animation_clock[0]))
        if character.resting:
            crawl.set_active(False)
        canvas.queue_draw()
    busy=[False]
    def dimensions(): return canvas.get_allocated_width(),canvas.get_allocated_height()
    def visible():
        return avatar_visible(perch.get_active(),follow.target is not None,False,False)
    last_region=[None]
    alpha_cache={};mask_cache={}
    def sprite(key):
        return corner_pix if key=='flight' else sheet.new_subpixbuf(*rectangle(key))
    def local_input_mask():
        keys=tuple(sorted(pose_blend.weights(),key=str))
        if keys not in mask_cache:
            for key in keys:
                if key not in alpha_cache:
                    pix=sprite(key);data=pix.get_pixels();stride=pix.get_rowstride();channels=pix.get_n_channels()
                    alpha_cache[key]=tuple(data[y*stride+x*channels+3] if pix.get_has_alpha() else 255 for y in range(208) for x in range(192))
            mask_cache[keys]=opaque_intersection([alpha_cache[key] for key in keys],192,208)
        return mask_cache[keys]
    def region():
        if args.experimental_single_window_head_input:head_refresh()
        if Layer and window.get_window():
            rects=local_input_mask() if visible() else ()
            key=(int(motion.x),int(motion.y),rects)
            if last_region[0]==key:return
            r=cairo.Region()
            for x,y,w,h in rects:r.union(cairo.RectangleInt(int(motion.x)+x,int(motion.y)+y,w,h))
            window.get_window().input_shape_combine_region(r,0,0);last_region[0]=key
    def refresh_overlay(*_):
        region();canvas.queue_draw()
        return False
    def draw(widget,cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0,0,0,0 if Layer else 1)
        cr.paint();cr.set_operator(cairo.OPERATOR_OVER)
        if not visible():return False
        flying=(motion.crawl or (perch.get_active() and not follow.arrived)) and drag[0] is None and not character.resting
        # One consistent airborne orientation avoids full-body flip snaps.
        cr.set_operator(cairo.OPERATOR_ADD)
        for key,opacity in pose_blend.weights().items():
            pix=sprite(key)
            Gdk.cairo_set_source_pixbuf(cr,pix,int(motion.x),int(motion.y))
            cr.paint_with_alpha(opacity)
        cr.set_operator(cairo.OPERATOR_OVER)
        return False
    canvas.connect('draw',draw)
    def size(_widget,_allocation):
        position=anchor.allocate(*dimensions())
        if position is not None:
            motion.x,motion.y=position;motion.base_y=motion.y
            follow.x,follow.y=motion.x,motion.y
        motion.bound(*dimensions());region()
        if bubble.window.get_visible():bubble.position()
    canvas.connect('size-allocate',size)
    transport=None
    if conversation_submit is None:
        transport=OmegaTransport([str(args.conversation_python),'-u','-B',str(args.conversation_runner)])
        conversation_submit=transport.submit
    bubble=ChatBubble(Gtk,Gdk,GLib,Layer,lambda:((motion.x,motion.y,192,208),dimensions()),submit=conversation_submit,reset=transport.reset if transport else None,quit_callback=lambda:close(),monitor=lambda:Gdk.Display.get_default().get_monitor_at_window(window.get_window()))
    def press(_widget,event):
        if event.button!=1:return False
        if motion.x<=event.x<motion.x+192 and motion.y<=event.y<motion.y+208:
            drag[0]=(event.x,event.y);moved[0]=False;return True
        return False
    def move(_widget,event):
        if drag[0] is None:return False
        dx,dy=event.x-drag[0][0],event.y-drag[0][1]
        moved[0]=moved[0] or abs(dx)+abs(dy)>2
        if dx or dy:
            perch.set_active(False);anchor.manual()
        motion.drag(dx,dy,*dimensions());drag[0]=(event.x,event.y)
        region();canvas.queue_draw();return True
    def release(_widget,event):
        if event.button!=1 or drag[0] is None:return False
        if not moved[0]:
            care('greet');bubble.show()
        drag[0]=None;return True
    canvas.connect('button-press-event',press);canvas.connect('motion-notify-event',move);canvas.connect('button-release-event',release)
    def head_activate(x,y):
        head_refresh()
        if not head_target[0].contains(x,y):return
        head_target[0].invalidate()
        bubble.show()
    def head_refresh():
        target=head_target[0]
        if target is None:return
        report=head_lease.current()
        eligible=(report is not None and tracker_proc[0] is not None and visible()
                  and perch.get_active() and follow.arrived and follow.phase=='perched'
                  and layers.requested=='bottom' and pose_blend.weights()=={'flight':1.0}
                  and not report.get('fullscreen',True) and not report.get('maximized',True)
                  and not tracker_buffer)
        if not eligible:target.invalidate();return
        try:
            a=window.get_window();b=target.window.get_window()
            if not a or not b or not window.get_mapped() or not target.window.get_mapped():raise ValueError('mapping')
            # Toolkit local origin equality is a compatibility check, NOT global coordinates.
            ao=a.get_origin();bo=b.get_origin()
            if len(ao)!=3 or len(bo)!=3 or not ao[0] or not bo[0] or tuple(ao)!=tuple(bo):raise ValueError('origin')
            size=dimensions()
            if size!=(target.canvas.get_allocated_width(),target.canvas.get_allocated_height()):raise ValueError('allocation')
            if size!=(report['observer_width'],report['observer_height']):raise ValueError('observer')
            actual_rect=tuple(report[k] for k in ('x','y','width','height'))
            if follow.route!=(actual_rect,tuple(size)):raise ValueError('Stale settled route')
            if (motion.x,motion.y)!=(report['x']-60,report['y']-65):raise ValueError('Unsettled new target')
            rects=head_region(head_alpha,192,208,(motion.x,motion.y),(12,10,62,54),
                              tuple(report[k] for k in ('x','y','width','height')),size,
                              enabled=True,perched=True,visible=True,settled=True,
                              mapping_verified=True,scene_exposure_verified=True)
            if target.rects!=rects:target.apply(rects,size)
        except (ValueError,TypeError,AttributeError,KeyError):target.invalidate()
    head_alpha=()
    if args.experimental_single_window_head_input:
        if (corner_pix.get_width(),corner_pix.get_height(),corner_pix.get_n_channels(),corner_pix.get_has_alpha())!=(192,208,4,True):raise ValueError('Unsupported head artwork')
        data=corner_pix.get_pixels();stride=corner_pix.get_rowstride()
        head_alpha=tuple(data[y*stride+x*4+3] for y in range(208) for x in range(192))
        head_target[0]=HeadTarget(Gtk,Gdk,Layer,cairo,head_activate)
    def stop_tracker():
        head_lease.invalidate()
        if head_target[0]:head_target[0].invalidate()
        proc=tracker_proc[0]
        if proc is not None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
            proc.stdout.close();tracker_proc[0]=None
    def tracker_input(_fd,condition):
        drained_bytes=0;drained_records=0
        try:
            while True:
                read_size=min(4096,16384-drained_bytes+1) if args.experimental_single_window_head_input else 4096
                try:data=os.read(tracker_proc[0].stdout.fileno(),read_size)
                except BlockingIOError:break
                if not data:
                    head_lease.invalidate()
                    if head_target[0]:head_target[0].invalidate()
                    follow.clear('Actual tracker stopped');last_report[0]=None;tracker_watch[0]=None
                    return False
                drained_bytes+=len(data)
                if args.experimental_single_window_head_input and drained_bytes>16384:raise ValueError('Tracker drain cap')
                tracker_buffer.extend(data)
                while b'\n' in tracker_buffer:
                    raw,_,remaining=tracker_buffer.partition(b'\n');tracker_buffer[:]=remaining
                    if args.experimental_single_window_head_input:
                        drained_records+=1
                        if drained_records>64:raise ValueError('Tracker record cap')
                        last_report[0]=consume_head_report(raw,parse_report,head_lease,head_target[0],last_report[0])
                    else:last_report[0]=parse_report(raw)
                if len(tracker_buffer)>MAX_LINE:raise ValueError('Tracker line exceeds cap')
        except (ValueError,OSError):
            follow.clear('Invalid actual tracker report');last_report[0]=None;stop_tracker();tracker_watch[0]=None
            return False
        if head_target[0]:
            if tracker_buffer:head_target[0].invalidate()
            head_refresh()
        return True
    if Layer:
        if not args.tracker.is_absolute() or not args.tracker.is_file():
            follow.clear('Actual geometry tracker unavailable')
        else:
            try:
                proc=subprocess.Popen([str(args.tracker)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
                head_lease.reset_for_new_helper()
                tracker_proc[0]=proc;os.set_blocking(proc.stdout.fileno(),False)
                tracker_watch[0]=GLib.io_add_watch(proc.stdout.fileno(),GLib.IO_IN|GLib.IO_HUP|GLib.IO_ERR,tracker_input)
            except OSError:follow.clear('Actual geometry tracker could not start')
    last=[time.monotonic()];poll=[0.0];ticks=[0]
    def tick():
        # Expire proxy leases even while animation is paused for conversation.
        if head_target[0]:head_refresh()
        if bubble.window.get_visible():
            now=time.monotonic();dt=now-last[0];last[0]=now
            # Pause travel while chatting, but finish a pose transition started
            # by the press/release so the avatar does not freeze as two ghosts.
            pose_blend.step(dt,paused=motion.paused)
            region()
            dirty=render_gate.update(visible(),motion.x,motion.y,pose_blend.weights())
            if dirty:canvas.queue_draw_area(*dirty)
            return True
        now=time.monotonic();dt=now-last[0];last[0]=now
        if args.events and now-poll[0]>=0.5:
            poll[0]=now
            try:
                new=read_event(args.events)
                label.set_text('Omega · '+new+' (reported state)')
            except (OSError,ValueError,TypeError):
                new='idle';label.set_text('Omega · no recent state report')
            if state[0]!=new:frame[0]=0
            state[0]=new
        if perch.get_active():
            report=last_report[0]
            if report is not None:
                if report['active']:
                    follow.update(tuple(report[k] for k in ('x','y','width','height')),tuple(report[k] for k in ('observer_width','observer_height')),dimensions(),fullscreen=report['fullscreen'],maximized=report['maximized'])
                else:follow.clear('No eligible active corner: '+report['reason'])
            if not motion.paused and not character.resting:follow.step(dt)
            if args.layered_flight and Layer:
                layers.set(follow.layer)
            motion.x,motion.y,motion.direction=follow.x,follow.y,follow.direction
            motion.bound(*dimensions());follow.x,follow.y=motion.x,motion.y
        if not motion.paused:
            ticks[0]+=1
            if ticks[0]%4==0:frame[0]+=1
            if not perch.get_active() and drag[0] is None and not character.resting:motion.step(dt,*dimensions())
        status=status_text(follow,enabled=perch.get_active(),paused=motion.paused,resting=character.resting)
        if args.layered_flight and perch.get_active() and follow.target is not None and not motion.paused and not character.resting:
            status={'approach':'Flying in front · toward an outside-window waypoint','settle':'Flying behind ordinary windows · toward the corner','perched':'Perched behind ordinary windows · head outside the active corner'}.get(follow.phase,status)
        if perch_status.get_text()!=status:perch_status.set_text(status)
        flying=(motion.crawl or (perch.get_active() and not follow.arrived)) and drag[0] is None and not character.resting
        if not motion.paused:animation_clock[0]+=max(0,min(dt,.1))
        pose_blend.set_target(pose_key(character,busy[0],state[0],flying,perch.get_active(),animation_clock[0]),instant=motion.paused)
        pose_blend.step(dt,paused=motion.paused)
        region()
        dirty=render_gate.update(visible(),motion.x,motion.y,pose_blend.weights())
        if dirty:canvas.queue_draw_area(*dirty)
        return True
    timer=GLib.timeout_add(31,tick)
    closing=[False]
    def close(*_):
        if closing[0]:return
        closing[0]=True;GLib.source_remove(timer)
        if tracker_watch[0] is not None:GLib.source_remove(tracker_watch[0])
        stop_tracker()
        if head_target[0]:head_target[0].close()
        bubble.close()
        if transport:
            try:transport.close()
            except RuntimeError as exc:print(str(exc),file=sys.stderr)
        window.destroy();Gtk.main_quit()
    window.connect('destroy',close)
    # Only the transparent character layer is mapped at login.
    window.show_all()
    if head_target[0]:head_target[0].window.show_all();head_target[0].invalidate()
    region();Gtk.main()
    os.close(instance_fd)
    return 0
if __name__=='__main__':raise SystemExit(main())
