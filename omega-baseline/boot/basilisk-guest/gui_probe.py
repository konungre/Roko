#!/usr/bin/python3
"""Exercise the real unchanged GTK application. Not a compositor pixel oracle.
Run in a real Wayland session. JSON reports describe widget-level observations;
external screenshots and compositor input are separate mandatory acceptance tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app-dir', default='/usr/share/roko/basilisk')
parser.add_argument('--output', default='/tmp/basilisk-gui-probe.json')
args = parser.parse_args()
sys.path.insert(0, args.app_dir)
import companion
from atlas import STATES, rectangle, look_rectangle
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

report = {'schema': 1, 'scope': 'real GTK widget probe; external compositor screenshot/input still required', 'checks': [], 'passed': False}
original_main = Gtk.main
sheet = GdkPixbuf.Pixbuf.new_from_file(str(companion.verify_asset()))

def digest(pixbuf):
    # Subpixbuf rowstride is the whole atlas; hash only visible row bytes.
    data = pixbuf.get_pixels()
    row = pixbuf.get_width() * pixbuf.get_n_channels()
    return hashlib.sha256(b''.join(data[y*pixbuf.get_rowstride():y*pixbuf.get_rowstride()+row] for y in range(pixbuf.get_height()))).hexdigest()

def check(name, passed, **values):
    report['checks'].append({'name': name, 'passed': bool(passed), **values})
    if not passed:
        raise AssertionError(name)

state = {}
def widgets(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from widgets(child)

def guarded(callback):
    def run():
        try:
            callback()
        except Exception as exc:
            report['error'] = str(exc)
            for window in Gtk.Window.list_toplevels():
                window.destroy()
            Gtk.main_quit()
        return False
    return run

def inspect():
    window, = [w for w in Gtk.Window.list_toplevels() if w.get_title() == 'Roko Basilisk']
    children = list(widgets(window))
    state.update(window=window, image=next(w for w in children if isinstance(w, Gtk.Image)), selector=next(w for w in children if isinstance(w, Gtk.ComboBoxText)), pause=next(w for w in children if isinstance(w, Gtk.ToggleButton)))
    # Runtime allocations are observations, not guessed absolute Wayland positions.
    report['layout'] = {'window_size': list(window.get_size()), 'scale_factor': window.get_scale_factor(), 'widgets': {}}
    for name in ('image', 'selector', 'pause'):
        widget = state[name]
        allocation = widget.get_allocation()
        report['layout']['widgets'][name] = {
            'allocation_in_parent': [allocation.x, allocation.y, allocation.width, allocation.height],
            'origin_in_window': list(widget.translate_coordinates(window, 0, 0)),
        }
    report['layout']['image_alignment'] = list(state['image'].get_alignment())
    report['layout']['image_padding'] = list(state['image'].get_padding())
    check('mapped-window', window.get_mapped() and window.get_window() is not None)
    display = Gdk.Display.get_default()
    check('wayland-backend', 'Wayland' in display.__gtype__.name, backend=display.__gtype__.name)
    state['first'] = digest(state['image'].get_pixbuf())
    state['selector'].set_active(1) # visibly differing running-right frames
    state['first'] = digest(state['image'].get_pixbuf())

def animated():
    current = digest(state['image'].get_pixbuf())
    check('timer-changes-frame', current != state['first'])
    state['pause'].set_active(True)
    state['paused'] = current

def paused():
    check('pause-holds-frame', digest(state['image'].get_pixbuf()) == state['paused'])
    # Select every animation and look direction, checking exact source pixel bytes.
    for index in range(25):
        state['selector'].set_active(index)
        area = rectangle(STATES[index], 0) if index < 9 else look_rectangle(index - 9)
        check('selection-' + str(index), digest(state['image'].get_pixbuf()) == digest(sheet.new_subpixbuf(*area)))
    state['selector'].set_active(1)
    state['first'] = digest(state['image'].get_pixbuf())
    state['pause'].set_active(False)

def resumed():
    check('resume-changes-frame', digest(state['image'].get_pixbuf()) != state['first'])
    state['window'].destroy() # invokes original application destroy/timer cleanup

def instrumented_main():
    for ms, callback in [(500, inspect), (950, animated), (1500, paused), (1950, resumed)]:
        GLib.timeout_add(ms, guarded(callback))
    original_main()

Gtk.main = instrumented_main
try:
    result = companion.main([])
    check('clean-close', result == 0 and not any(w.get_title() == 'Roko Basilisk' for w in Gtk.Window.list_toplevels()))
    report['passed'] = len(report['checks']) == 31 and all(c['passed'] for c in report['checks']) and 'error' not in report
except Exception as exc:
    report['error'] = str(exc)
finally:
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print('ROKO_BASILISK_GTK_PROBE ' + json.dumps(report), flush=True)
sys.exit(0 if report['passed'] else 1)
