"""Small storage overlay and exact init transformation. No archive, image or VM creation."""
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import stat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()

def desktop_entry(original):
    before=b'--state-dir /root/.local/state/roko'
    if original.count(before)!=1 or b'--avatar-events /run/user/0/roko/avatar.json' not in original:
        raise ValueError('Expected genuine avatar desktop entry')
    return original.replace(before,b'--state-dir /var/lib/roko')

def derive_init(data):
    before=b'/usr/bin/dbus-daemon --config-file=/etc/dbus-1/roko-session.conf --fork || fail dbus'
    if data.count(before)!=1 or data.count(b'    echo ROKO_SESSION_POWER_OFF')!=1:
        raise ValueError('Unexpected session init hooks')
    mount=(b'/usr/libexec/roko-storage-mount || fail storage-mount\n'
           b'/usr/bin/python3.13 -u /usr/libexec/roko-storage-observe.py >/dev/console 2>&1 &\n'
           b'storage_observer_pid=$!\n')
    data=data.replace(before,mount+before)
    cleanup=(b'    [ -z "${storage_observer_pid:-}" ] || $BB kill "$storage_observer_pid" 2>/dev/null\n'
             b'    /usr/libexec/roko-storage-unmount || echo ROKO_DESKTOP_STORAGE_FAILED unmount\n')
    return data.replace(b'    echo ROKO_SESSION_POWER_OFF',cleanup+b'    echo ROKO_SESSION_POWER_OFF')

def prepare(original_desktop, original_wrapper=None):
    spec=importlib.util.spec_from_file_location('desktop_ext4_inputs',ROOT/'boot/filesystem-guest/build.py')
    fs=importlib.util.module_from_spec(spec); spec.loader.exec_module(fs)
    _,kernel,_,modules,order,sources=fs.inputs()
    files={}
    def put(path,data,mode): files[path]=(data,stat.S_IFREG|mode,0,0)
    for source,dest in [('mount.sh','usr/libexec/roko-storage-mount'),('unmount.sh','usr/libexec/roko-storage-unmount'),('observe.py','usr/libexec/roko-storage-observe.py')]:
        put(dest,(HERE/source).read_bytes(),0o755)
    if original_wrapper is None:
        put('usr/share/applications/roko.desktop',desktop_entry(original_desktop),0o444)
    else:
        if original_desktop.splitlines().count(b'Exec=/usr/bin/roko-console-fixture')!=1:
            raise ValueError('Expected exact tested console fixture desktop entry')
        put('usr/share/applications/roko.desktop',original_desktop,0o444)
        put('usr/bin/roko-console-fixture',desktop_entry(original_wrapper),0o755)
    put('etc/storage-module-order',('\n'.join(order)+'\n').encode(),0o444)
    for name,record in modules.items():
        put('storage-modules/'+name+'.ko',lzma.decompress((ROOT/record['path']).read_bytes()),0o444)
    provenance={'kernel_release':kernel,'modules':modules,'sources':sources,
                'scripts':{name:sha((HERE/name).read_bytes()) for name in ['overlay.py','mount.sh','unmount.sh','observe.py','image.py','formatter.py','storage.py']},
                'desktop_before_sha256':sha(original_desktop),'desktop_after_sha256':sha(files['usr/share/applications/roko.desktop'][0])}
    if original_wrapper is not None:
        provenance['wrapper_before_sha256']=sha(original_wrapper)
        provenance['wrapper_after_sha256']=sha(files['usr/bin/roko-console-fixture'][0])
    return files,provenance
