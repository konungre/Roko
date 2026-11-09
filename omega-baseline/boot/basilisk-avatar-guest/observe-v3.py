#!/usr/bin/env python3
"""Read-only GTK observation harness; delegates unchanged companion.main().

Usage: python3 wrapper.py /usr/share/roko/basilisk [--overlay ...]
Emits JSON records prefixed ROKO_AVATAR_OBSERVE_V1 to stdout. Never injects input.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

if len(sys.argv) < 2:
    raise SystemExit('Usage: wrapper.py COMPANION_DIRECTORY [companion arguments]')
base = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(base))
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio
import cairo
import companion

PREFIX = 'ROKO_AVATAR_OBSERVE_V2 '
start = time.monotonic()
sequence = 0

def emit(kind, **fields):
    global sequence
    sequence += 1
    print(PREFIX + json.dumps(dict(sequence=sequence, elapsed_ms=round((time.monotonic()-start)*1000),
                                   kind=kind, **fields), sort_keys=True), flush=True)

def rect(value):
    return dict(x=value.x, y=value.y, width=value.width, height=value.height)

# Observe actual arguments to the real GDK setter, then immediately forward them.
# These are requested input regions, not proof that the compositor applied them.
original_region = Gdk.Window.input_shape_combine_region
previous_regions = {}

def observed_region(window, region, offset_x, offset_y):
    result = original_region(window, region, offset_x, offset_y)
    rectangles = None if region is None else [rect(region.get_rectangle(i)) for i in range(region.num_rectangles())]
    key = id(window)
    value = dict(rectangles=rectangles, offset_x=offset_x, offset_y=offset_y)
    if previous_regions.get(key) != value:
        previous_regions[key] = value
        emit('requested_input_region', **value)
    return result

Gdk.Window.input_shape_combine_region = observed_region

# Hooks observe calls without changing arguments, results or exception behavior.
original_launch = Gio.DesktopAppInfo.launch
original_set_text = Gtk.Label.set_text
observed_buttons = set()

def observed_launch(app, *args, **kwargs):
    emit('desktop_launch_call', desktop_id=app.get_id(), executable=app.get_executable())
    try:
        result = original_launch(app, *args, **kwargs)
    except Exception as exc:
        emit('desktop_launch_error', desktop_id=app.get_id(), error_type=type(exc).__name__, error=str(exc))
        raise
    emit('desktop_launch_return', desktop_id=app.get_id(), result=result,
         child_exit_observation='unavailable: launch result is not process-exit evidence')
    return result

def observed_set_text(label, text):
    before = label.get_text()
    result = original_set_text(label, text)
    if before != label.get_text():
        emit('label_text_changed', before=before, after=label.get_text())
    return result

Gio.DesktopAppInfo.launch = observed_launch
Gtk.Label.set_text = observed_set_text

def observe_clicked(button):
    emit('button_clicked', label=button.get_label(),
         active=button.get_active() if isinstance(button, Gtk.ToggleButton) else None)

def describe(widget, top, path):
    if isinstance(widget, Gtk.Button) and widget not in observed_buttons:
        widget.connect_after('clicked', observe_clicked)
        observed_buttons.add(widget)
    item = dict(path=path, type=type(widget).__name__, allocation=rect(widget.get_allocation()),
                visible=widget.get_visible(), mapped=widget.get_mapped(), sensitive=widget.get_sensitive())
    translated = widget.translate_coordinates(top, 0, 0)
    if translated is not None:
        item['window_origin'] = list(translated)
    if isinstance(widget, Gtk.Label):
        item['text'] = widget.get_text()
    elif isinstance(widget, Gtk.Button):
        item['label'] = widget.get_label()
    if isinstance(widget, Gtk.ToggleButton):
        item['active'] = widget.get_active()
    if isinstance(widget, Gtk.Container):
        item['children'] = [describe(child, top, path + '/' + str(i)) for i, child in enumerate(widget.get_children())]
    return item

def observe():
    windows = []
    for index, top in enumerate(Gtk.Window.list_toplevels()):
        windows.append(dict(title=top.get_title(), size=list(top.get_size()),
                            mapped=top.get_mapped(), visible=top.get_visible(),
                            tree=describe(top, top, str(index))))
    emit('snapshot', windows=windows)
    return True

emit('start', companion_sha256=hashlib.sha256((base/'companion.py').read_bytes()).hexdigest(),
     sprite_sha256=hashlib.sha256((base/'assets/roko.png').read_bytes()).hexdigest(),
     argv=sys.argv[2:], input_region_observation='actual setter arguments, not compositor readback')
watch = GLib.timeout_add(500, observe)
try:
    result = companion.main(sys.argv[2:])
    emit('return', exit_code=result)
finally:
    GLib.source_remove(watch)
    Gdk.Window.input_shape_combine_region = original_region
    Gio.DesktopAppInfo.launch = original_launch
    Gtk.Label.set_text = original_set_text
raise SystemExit(result)
