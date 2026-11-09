#!/usr/bin/env python3
"""Build a separate verified GTK/Python companion overlay. Never starts a VM."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'build-src/basilisk-stage'
spec = importlib.util.spec_from_file_location('cosmic_guest_build', ROOT / 'boot/cosmic-guest/build.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def prepare():
    output = STAGE / 'overlay'
    if output.exists():
        raise SystemExit('Refusing existing overlay: ' + str(output))
    lockdata = (STAGE / 'debian-files.lock.json').read_bytes()
    c = base.Closure(STAGE / 'sysroot', json.loads(lockdata))
    # GI resolves typelibs to dlopened libraries, which are not all ELF NEEDED.
    for path in ['usr/bin/python3', 'usr/bin/python3.13',
                 'usr/lib/x86_64-linux-gnu/libgtk-3.so.0',
                 'usr/lib/x86_64-linux-gnu/libgdk-3.so.0',
                 'usr/lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0',
                 'usr/lib/x86_64-linux-gnu/libgirepository-1.0.so.1',
                 'usr/lib/x86_64-linux-gnu/glib-2.0/glib-compile-schemas']:
        c.add(path)
    for path in ['usr/lib/python3.13', 'usr/lib/python3/dist-packages/gi',
                 'usr/lib/x86_64-linux-gnu/girepository-1.0',
                 'usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0',
                 'usr/share/glib-2.0/schemas', 'usr/share/gtk-3.0']:
        c.tree(path)
    for name in sorted(c.lock):
        if name.startswith('usr/share/icons/Adwaita/'):
            c.add(name)
    for p in json.loads((STAGE / 'debian-packages.lock.json').read_text())['packages']:
        path = 'usr/share/doc/' + p['package'] + '/copyright'
        if c.resolve(path) in c.lock:
            c.add(path)
    subprocess.run(['python3', str(ROOT/'desktop/basilisk/stage.py'), str(output)], check=True)
    for name, (data, mode) in c.files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(stat.S_IMODE(mode))
    # Official verified compiler writes only this private overlay's schema cache.
    subprocess.run([str(output/'lib64/ld-linux-x86-64.so.2'),
                    '--library-path', str(output/'usr/lib/x86_64-linux-gnu'),
                    str(output/'usr/lib/x86_64-linux-gnu/glib-2.0/glib-compile-schemas'),
                    '--strict', str(output/'usr/share/glib-2.0/schemas')], check=True)
    # Keep the probe separate from the unchanged application, no autostart.
    probe = output / 'usr/libexec/roko-basilisk-gui-probe.py'
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes((ROOT/'boot/basilisk-guest/gui_probe.py').read_bytes())
    probe.chmod(0o755)
    receipts = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            receipts.append({'path': str(path.relative_to(output)), 'kind': 'file', 'sha256': base.sha(path.read_bytes()), 'mode': stat.S_IMODE(path.stat().st_mode)})
    result = {'schema': 1, 'source_lock_sha256': base.sha(lockdata), 'files': receipts, 'runtime_sources': c.sources, 'elfs': c.elfs, 'bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file()), 'scope': 'uninstalled separate overlay; no VM run and no real GTK rendering claimed'}
    (STAGE/'overlay.lock.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'files': len(receipts), 'bytes': result['bytes'], 'overlay': str(output)}))

if __name__ == '__main__':
    prepare()
