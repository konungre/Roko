#!/bin/sh
# Only workspace-local staged official Debian libraries; no host installation.
set -eu
cd "$(dirname "$0")/../.."
S="$PWD/build-src/basilisk-stage/overlay"
export PYTHONHOME="$S/usr"
export PYTHONPATH="$S/usr/lib/python3/dist-packages"
export GI_TYPELIB_PATH="$S/usr/lib/x86_64-linux-gnu/girepository-1.0"
export LD_LIBRARY_PATH="$S/usr/lib/x86_64-linux-gnu"
export GSETTINGS_SCHEMA_DIR="$S/usr/share/glib-2.0/schemas"
# Do not let host MIME or pixbuf-loader data mask missing guest data.
E="$PWD/build-src/basilisk-stage/headless-empty-data"
mkdir -p "$E"
: > "$E/loaders.cache"
export XDG_DATA_HOME="$E"
export XDG_DATA_DIRS="$PWD/build-src/basilisk-stage/mime-overlay-v1/usr/share"
export GDK_PIXBUF_MODULE_FILE="$E/loaders.cache"
export GDK_PIXBUF_MODULEDIR="$E"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
"$S/lib64/ld-linux-x86-64.so.2" "$S/usr/bin/python3" - <<'PY'
import hashlib, json, sys
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, Gio
sys.path.insert(0,'desktop/basilisk')
from atlas import STATES, COUNTS, rectangle, look_rectangle
from companion import verify_asset
sheet=GdkPixbuf.Pixbuf.new_from_file(str(verify_asset()))
checks=0
for i,state in enumerate(STATES):
    for frame in range(COUNTS[i]):
        p=sheet.new_subpixbuf(*rectangle(state,frame))
        assert (p.get_width(),p.get_height())==(192,208)
        checks+=1
for i in range(16):
    p=sheet.new_subpixbuf(*look_rectangle(i))
    assert (p.get_width(),p.get_height())==(192,208)
    checks+=1
assert Gio.SettingsSchemaSource.get_default().lookup('org.gtk.Settings.FileChooser',True)
print(json.dumps({'passed':True,'gtk_version':[Gtk.get_major_version(),Gtk.get_minor_version(),Gtk.get_micro_version()],'atlas_dimensions':[sheet.get_width(),sheet.get_height()],'decoded_cells':checks,'gtk_schema_present':True,'scope':'headless staged GTK import, original PNG decode and schema lookup only; no rendering/input claim'}))
PY
