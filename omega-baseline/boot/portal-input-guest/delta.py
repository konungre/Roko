"""Separate guest-only protocol diagnostic seed; no assembly/VM on import."""
import hashlib,importlib.util,json,stat
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1]
s=importlib.util.spec_from_file_location('portal_base_delta',R/'boot/test-delta-root/prepare.py');base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
ROOT_ID=base.ROOT_ID;ROOT_SHA=base.ROOT_SHA
WRAPPER=b'''#!/bin/sh
# Private guest diagnostic only; upstream executable and args unchanged.
export ICED_BACKEND=tiny-skia WAYLAND_DEBUG=client
exec >/dev/console 2>&1
echo ROKO_PORTAL_INPUT_DIAGNOSTIC_START
exec /usr/libexec/xdg-desktop-portal-cosmic "$@"
'''
def sha(x):return hashlib.sha256(x).hexdigest()
def prepare(which='files'):
 if which!='files':raise ValueError('Files-only input diagnostic')
 entries,receipt=base.prepare('files');name='portal-debug/launch.sh';record={'path':name,'sha256':sha(WRAPPER),'mode':0o755,'bytes':len(WRAPPER),'source':str(H/'delta.py')+'::WRAPPER'}
 records=receipt['records']+[record];records.sort(key=lambda r:r['path'])
 identity={k:receipt[k] for k in ['root_build_id','root_sha256','selection','corner_inputs_sha256']};identity.update(source_sha256=sha(Path(__file__).read_bytes()),records=records,base_delta_id=receipt['delta_id']);did=sha(json.dumps(identity,sort_keys=True).encode())
 entries['roko-test-seed/portal-debug']=(b'',stat.S_IFDIR|0o700,0,0)
 entries['roko-test-seed/'+name]=(WRAPPER,stat.S_IFREG|0o755,0,0)
 entries['roko-test-sha256']=((''.join(r['sha256']+'  '+r['path']+'\n' for r in records)).encode(),stat.S_IFREG|0o444,0,0)
 entries['roko-test-install.sh']=(base.installer(records,did),stat.S_IFREG|0o700,0,0)
 return entries,dict(identity,delta_id=did,payload_bytes=receipt['payload_bytes']+len(WRAPPER),assembly_performed=False)
def derive_init(original):
 init=base.derive_init(original);hook=base.HOOK
 extra=b'''[ -f /newroot/usr/libexec/roko-cosmic-portal ] && [ ! -L /newroot/usr/libexec/roko-cosmic-portal ] || fail portal-wrapper-target
$BB mount --bind /newroot/run/roko-test-overlay/portal-debug/launch.sh /newroot/usr/libexec/roko-cosmic-portal || fail portal-debug-bind
$BB mount -o remount,bind,ro,nodev,nosuid /newroot/usr/libexec/roko-cosmic-portal || fail portal-debug-readonly
echo ROKO_PORTAL_INPUT_BIND_READY
'''
 return init.replace(hook,extra+hook)
