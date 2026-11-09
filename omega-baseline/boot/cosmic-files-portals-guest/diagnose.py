#!/usr/bin/python3.13
"""Opt-in guest fixture/evidence helper. Never performs GUI operations."""
import argparse, configparser, hashlib, json, os, pathlib, stat
from urllib.parse import unquote
ROOT = pathlib.Path('/root/.local/share/roko-portal-fixture')
CONTENT = b'ROKO_LOCAL_FILE_FIXTURE_v1\n'
ENV_KEYS = {'ICED_BACKEND', 'WAYLAND_DEBUG', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'XDG_CURRENT_DESKTOP'}
EXES = {'cosmic-files', 'cosmic-files-applet', 'xdg-desktop-portal-cosmic', 'xdg-desktop-portal', 'xdg-desktop-portal-gtk'}

def safe(path):
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise RuntimeError('Refusing symlink: ' + str(part))
    return path

def exact(path):
    safe(path)
    if not path.is_file() or path.read_bytes() != CONTENT:
        raise RuntimeError('Missing or changed fixture: ' + str(path))
    return {'path': str(path), 'bytes': len(CONTENT), 'sha256': hashlib.sha256(CONTENT).hexdigest()}

def processes():
    out = []
    for p in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            exe = os.readlink(p / 'exe')
            if pathlib.Path(exe).name not in EXES:
                continue
            env = {}
            for item in (p / 'environ').read_bytes().split(b'\0'):
                key, _, value = item.partition(b'=')
                name = key.decode(errors='replace')
                if name in ENV_KEYS:
                    env[name] = value.decode(errors='replace')
            threads = []
            for t in (p / 'task').glob('[0-9]*'):
                try:
                    fields = (t / 'stat').read_text().rsplit(')', 1)[1].split()
                    threads.append({'tid': int(t.name), 'state': fields[0], 'utime_ticks': int(fields[11]), 'stime_ticks': int(fields[12]), 'wchan': (t / 'wchan').read_text().strip()})
                except (OSError, IndexError, ValueError):
                    threads.append({'tid': int(t.name), 'vanished_or_unreadable': True})
            out.append({'pid': int(p.name), 'exe': exe, 'selected_environment': env, 'threads': threads})
        except OSError:
            continue
    return {'processes': out, 'read_only': True}

BUS_NAMES = (
    'org.freedesktop.portal.Desktop',
    'org.freedesktop.impl.portal.desktop.cosmic',
    'org.freedesktop.impl.portal.desktop.gtk',
    'org.freedesktop.FileManager1',
)

def owner_records(query, evidence):
    """Pure binding logic; query is a read-only bus-daemon method adapter."""
    by_pid = {p['pid']: p for p in evidence['processes']}
    records = []
    for name in BUS_NAMES:
        record = {'name': name}
        try:
            owner = query('GetNameOwner', name)
            record['unique_owner'] = owner
            pid = query('GetConnectionUnixProcessID', owner)
            record['pid'] = pid
            record['owner_stable'] = query('GetNameOwner', name) == owner
            record['process_evidence'] = by_pid.get(pid)
            record['process_evidence_status'] = 'matched' if pid in by_pid else 'not_allowlisted_or_vanished_or_unreadable'
        except Exception as exc:
            record['status'] = 'missing_owner' if 'org.freedesktop.DBus.Error.NameHasNoOwner' in str(exc) else 'query_failed'
            record['error'] = str(exc)
        else:
            record['status'] = 'owned' if record['owner_stable'] else 'owner_changed_during_snapshot'
        records.append(record)
    return {'bus_owners': records, 'read_only': True, 'activation_requested': False,
            'dialog_backend_proven_by_ownership_alone': False}

def bus_owners():
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def query(method, value):
        return bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                             'org.freedesktop.DBus', method,
                             GLib.Variant('(s)', (value,)), None,
                             Gio.DBusCallFlags.NO_AUTO_START, 5000, None).unpack()[0]
    return owner_records(query, processes())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'inspect', 'processes', 'bus-owners', 'assert-copy', 'assert-rename', 'assert-trash'])
    a = parser.parse_args()
    marker = safe(pathlib.Path('/run/roko-files-portals-guest'))
    if not marker.is_file():
        raise RuntimeError('Guest-only regular marker absent')
    safe(ROOT)
    original = ROOT / 'input.txt'
    copied = ROOT / 'scratch/input.txt'
    renamed = ROOT / 'scratch/renamed.txt'
    if a.mode == 'bus-owners':
        result = bus_owners()
    elif a.mode == 'processes':
        result = processes()
    elif a.mode == 'prepare':
        ROOT.mkdir(parents=True, exist_ok=True)
        safe(original)
        if original.exists():
            result = exact(original)
        else:
            with original.open('xb') as f:
                f.write(CONTENT)
            result = exact(original)
        # Deliberately do not create scratch, copy, rename, or trash anything.
    elif a.mode == 'inspect':
        result = {'original': exact(original), 'entries': []}
        for p in sorted(ROOT.rglob('*')):
            safe(p)
            result['entries'].append({'relative_path': str(p.relative_to(ROOT)), 'type': 'directory' if p.is_dir() else 'file', 'bytes': p.stat().st_size})
    else:
        result = {'original': exact(original), 'stage': a.mode, 'passed': True}
        if a.mode == 'assert-copy':
            result['copy'] = exact(copied)
        elif a.mode == 'assert-rename':
            if safe(copied).exists():
                raise RuntimeError('Pre-rename path still exists')
            result['renamed'] = exact(renamed)
        else:
            if safe(copied).exists() or safe(renamed).exists():
                raise RuntimeError('Working copy still exists outside Trash')
            trash = safe(pathlib.Path('/root/.local/share/Trash'))
            matches = []
            for info in (trash / 'info').glob('*.trashinfo'):
                safe(info)
                c = configparser.ConfigParser(interpolation=None)
                c.read_string(info.read_text())
                if unquote(c.get('Trash Info', 'Path', fallback='')) == str(renamed):
                    item = exact(trash / 'files' / info.name.removesuffix('.trashinfo'))
                    item['trashinfo'] = str(info)
                    item['deletion_date'] = c.get('Trash Info', 'DeletionDate', fallback='')
                    if not item['deletion_date']:
                        raise RuntimeError('Trash metadata lacks deletion date')
                    matches.append(item)
            if len(matches) != 1:
                raise RuntimeError('Expected exactly one genuine Trash entry; found ' + str(len(matches)))
            result['trash'] = matches[0]
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
