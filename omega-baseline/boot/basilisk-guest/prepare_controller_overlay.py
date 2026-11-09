#!/usr/bin/env python3
"""Stage the genuine stdlib Roko console for the separate avatar guest. No VM."""
import argparse
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'build-src/omega-avatar-controller-stage/overlay-v1'
FILES = {name: 'opt/roko/' + name for name in (
    'scripts/roko.py', 'adapters/working_state.py', 'adapters/state_store.py',
    'adapters/package_inventory.py', 'adapters/avatar_events.py',
    'granite-model.lock.json', 'boot/tooling-packages.lock.json', 'os-profile.json')}
COMMAND = ['/usr/bin/cosmic-term', '--no-daemon', '-e', '/usr/bin/python3.13',
           '/opt/roko/scripts/roko.py', '--state-dir', '/root/.local/state/roko',
           '--avatar-events', '/run/user/0/roko/avatar.json', 'console']
DESKTOP = '''[Desktop Entry]
Type=Application
Version=1.0
Name=Omega task console
Comment=Foreground Roko evidence and proposal console; no autonomous actions
Exec=''' + ' '.join(COMMAND) + '''
TryExec=/usr/bin/cosmic-term
Icon=utilities-terminal
Terminal=false
Categories=Utility;Science;
StartupNotify=false
'''
README = '''# Omega console in the disposable avatar guest

The avatar's Open Omega console button opens this genuine foreground Roko CLI
through roko.desktop and COSMIC Terminal. It never runs task work on its own.
Type help using --help at the console, or quit to exit. This is not a shell.

Task checkpoints: /root/.local/state/roko (volatile in this disposable guest).
Cosmetic event: /run/user/0/roko/avatar.json. Guest init must create its parent
owned by the shared session UID 0 with mode 0700. No task text enters this file.
Only user-invoked active checks/inference emit a heartbeat; quiet events expire.

Create, evidence, propose, check, close, show, list, status and packages use only
the already-staged Python 3.13 stdlib. Inference, native attention and package
archive verification are unavailable here and fail closed. No model, SWI-Prolog,
native ECAN runtime, package archives, installer, scheduler, or downloader is
included. The package inventory describes recorded workspace artifacts, not
installed guest packages. The source profile/status remain conservative; they
are not evidence of a new boot, durable task persistence, or a finished OS.

This desktop entry has explicit argument boundaries, invokes no shell command,
and is not registered for autostart. It changes no action permissions. It uses
the guest's existing Python interpreter, not the host bin/roko seccomp wrapper.
The guest launch must retain its separate no-network VM policy.
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(output=DEFAULT_OUTPUT):
    output = Path(output)
    lock = output.with_suffix('.lock.json')
    if output.exists() or output.is_symlink() or lock.exists() or lock.is_symlink():
        raise ValueError('Refusing an existing controller overlay or lock')
    payloads = {destination: (ROOT / source).read_bytes() for source, destination in FILES.items()}
    payloads['usr/share/applications/roko.desktop'] = DESKTOP.encode()
    payloads['opt/roko/AVATAR_CONSOLE.md'] = README.encode()
    output.mkdir(parents=True, mode=0o755)
    records = []
    for name, data in sorted(payloads.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
        records.append({'path': name, 'kind': 'file', 'sha256': sha(data), 'mode': stat.S_IMODE(path.stat().st_mode), 'bytes': len(data)})
    result = {'schema': 1, 'files': records, 'bytes': sum(record['bytes'] for record in records),
              'preparer_sha256': sha(Path(__file__).read_bytes()), 'source_files': FILES,
              'desktop_argv': COMMAND, 'required_guest_uid': 0,
              'required_private_event_directory': '/run/user/0/roko',
              'required_event_directory_mode': 0o700,
              'required_runtime': 'Existing verified GTK overlay Python 3.13 and its stdlib; no new interpreter',
              'scope': 'Separate uninstalled genuine controller overlay; no VM run, model, downloads, autonomy or action dispatch'}
    lock.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
