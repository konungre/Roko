#!/usr/bin/env python3
"""Exercise the copied real CLI under staged guest Python 3.13, without a VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE = ROOT / 'build-src/omega-avatar-controller-stage'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_overlay(path, lock):
    raw = lock.read_bytes()
    manifest = json.loads(raw)
    for record in manifest['files']:
        name = Path(record['path'])
        assert not name.is_absolute() and '..' not in name.parts, record['path']
        file = path / name
        assert not file.is_symlink() and file.is_file(), str(file)
        assert record['kind'] == 'file' and sha(file.read_bytes()) == record['sha256'], str(file)
        assert stat.S_IMODE(file.stat().st_mode) == record['mode'], str(file)
    return sha(raw), len(manifest['files'])


def check(overlay, runtime, reader):
    overlay_hash, overlay_count = verified_overlay(overlay, overlay.with_suffix('.lock.json'))
    runtime_hash, runtime_count = verified_overlay(runtime, runtime.with_suffix('.lock.json'))
    env = {key: value for key, value in os.environ.items() if key not in
           {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONINSPECT'}}
    env.update(PYTHONHOME=str(runtime / 'usr'), PYTHONPATH=str(runtime / 'usr/lib/python3/dist-packages'),
               GI_TYPELIB_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu/girepository-1.0'),
               PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    prefix = [str(runtime / 'lib64/ld-linux-x86-64.so.2'), '--library-path',
              str(runtime / 'usr/lib/x86_64-linux-gnu'), str(runtime / 'usr/bin/python3.13')]

    def python(*args, cwd=None, input=None):
        return subprocess.run([*prefix, *map(str, args)], env=env, cwd=cwd, input=input,
                              capture_output=True, text=True, timeout=15)

    info = python('-c', "import sys,json,fcntl,threading,tempfile,math; print(json.dumps({'version':sys.version,'json':json.__file__,'fcntl':getattr(fcntl,'__file__','built-in'),'threading':threading.__file__,'tempfile':tempfile.__file__}))")
    assert info.returncode == 0, info.stderr
    observed = json.loads(info.stdout)
    assert observed['version'].startswith('3.13.'), observed
    assert observed['json'].startswith(str(runtime / 'usr')), observed
    assert observed['threading'].startswith(str(runtime / 'usr')), observed
    # GLib parses the exact desktop Exec string, without launching a terminal.
    desktop = python('-c', '''import json,sys
from gi.repository import GLib
k=GLib.KeyFile(); k.load_from_file(sys.argv[1],GLib.KeyFileFlags.NONE)
ok,args=GLib.shell_parse_argv(k.get_string('Desktop Entry','Exec'))
assert ok and not k.get_boolean('Desktop Entry','Terminal')
assert args[:4]==['/usr/bin/cosmic-term','--no-daemon','-e','/usr/bin/python3.13']
assert args[4:]==['/opt/roko/scripts/roko.py','--state-dir','/root/.local/state/roko','--avatar-events','/run/user/0/roko/avatar.json','console']
print(json.dumps({'parsed_argv':args,'terminal':False,'launch_attempted':False}))
''', overlay / 'usr/share/applications/roko.desktop')
    assert desktop.returncode == 0, desktop.stderr
    desktop_report = json.loads(desktop.stdout)
    calls = []

    with tempfile.TemporaryDirectory(prefix='omega-avatar-python313-') as temporary:
        base = Path(temporary)
        events = base / 'events'
        events.mkdir(mode=0o700)
        event = events / 'avatar.json'
        state = base / 'state'
        cli = overlay / 'opt/roko/scripts/roko.py'

        def call(command, *args, code=0, expected=None, input=None):
            result = python(cli, '--state-dir', state, '--avatar-events', event,
                            command, *args, cwd=base, input=input)
            assert result.returncode == code, (command, result.returncode, result.stderr)
            row = {'command': command, 'exit_code': code}
            if expected is not None:
                data = json.loads(event.read_text())
                assert set(data) == {'version', 'state', 'time'} and data['version'] == 1, data
                assert data['state'] == expected, (command, data)
                assert stat.S_IMODE(event.stat().st_mode) == 0o600 and event.stat().st_uid == os.getuid()
                assert event.stat().st_size <= 1024
                read = python('-c', '''import importlib.util,sys
s=importlib.util.spec_from_file_location('reader',sys.argv[1]); m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
print(m.read_event(sys.argv[2]))
''', reader, event)
                assert read.returncode == 0 and read.stdout.strip() == expected, read.stderr
                row['companion_read_state'] = expected
            calls.append(row)
            return result

        data = json.loads(call('status', expected='idle').stdout)
        assert not data['model_file_present'] and not data['action_dispatch'] and not data['autonomy']
        packages = json.loads(call('packages', expected='idle').stdout)
        assert packages['package_count'] > 0 and not packages['authorizes_installation']
        assert not packages['inventory']['host_dpkg_observed'] and not packages['inventory']['archives_verified']
        call('create', 'math', '--goal', 'Synthetic arithmetic', expected='waiting')
        call('evidence', 'math', 'src', '--source', 'fixture', '--text', 'Arithmetic: 7 * 8.', expected='waiting')
        call('propose', 'math', '--tool', 'record_answer', '--arguments', '{"text":"55"}', '--evidence', 'src', expected='review')
        call('check', 'math', '--checker', 'arithmetic', expected='failed')
        call('close', 'math', code=2, expected='failed')
        call('propose', 'math', '--tool', 'record_answer', '--arguments', '{"text":"56"}', '--evidence', 'src', expected='review')
        call('check', 'math', '--checker', 'arithmetic', expected='review')
        call('close', 'math', expected='complete')
        value = json.loads(call('show', 'math', expected='idle').stdout)['state']
        assert value['phase'] == 'closed' and value['executed_actions'] == 0 and not value['verification']['authorizes_actions']
        call('create', 'quote', '--goal', 'Synthetic quotation', expected='waiting')
        evidence = base / 'text.txt'
        evidence.write_text('Zoë: ready')
        call('evidence', 'quote', 'src', '--source', 'local:fixture', '--file', evidence, expected='waiting')
        call('propose', 'quote', '--tool', 'record_answer', '--arguments', '{"text":"Zoë: ready"}', '--evidence', 'src', expected='review')
        call('check', 'quote', '--checker', 'quote', expected='review')
        call('close', 'quote', expected='complete')
        call('create', 'invoice', '--goal', 'Synthetic invoice', expected='waiting')
        call('evidence', 'invoice', 'src', '--source', 'fixture', '--text', 'Invoice A17; total 42.50.', expected='waiting')
        call('propose', 'invoice', '--tool', 'record_invoice', '--arguments', '{"invoice":"A17","total":"42.50"}', '--evidence', 'src', expected='review')
        call('check', 'invoice', '--checker', 'invoice', expected='review')
        call('close', 'invoice', expected='complete')
        call('create', 'missing-model', '--goal', 'Fail closed without inference', expected='waiting')
        call('evidence', 'missing-model', 'src', '--source', 'fixture', '--text', 'ready', expected='waiting')
        call('propose', 'missing-model', '--tool', 'record_answer', '--arguments', '{"text":"ready"}', '--evidence', 'src', expected='review')
        failure = call('infer', 'missing-model', '--tool', 'record_answer', '--evidence', 'src', '--prompt', 'Synthetic prompt', code=2, expected='failed')
        assert 'Local inference runtime/model unavailable' in failure.stderr and 'no download was attempted' in failure.stderr
        shown = json.loads(call('show', 'missing-model', expected='idle').stdout)['state']
        assert shown['proposal'] is None and shown['executed_actions'] == 0
        assert len(json.loads(call('list', expected='idle').stdout)) == 4
        call('create', 'math', '--goal', 'duplicate', code=3, expected='failed')
        failure = call('attention', '--candidates', '[]', code=2, expected='failed')
        assert 'Native ECAN adapter unavailable' in failure.stderr
        failure = call('packages', '--verify', code=2, expected='failed')
        assert 'Missing or size-mismatched archive' in failure.stderr
        console = call('console', input='status\nquit\n', expected='idle')
        assert 'Roko foreground console.' in console.stdout and '"action_dispatch": false' in console.stdout
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in state.glob('*.json'))

    return {'passed': True, 'scope': 'Host-executed staged guest Python3.13 and genuine copied CLI; no display, VM or persistence claim',
            'overlay_lock_sha256': overlay_hash, 'overlay_files_verified': overlay_count,
            'runtime_lock_sha256': runtime_hash, 'runtime_files_verified': runtime_count,
            'reader_sha256': sha(reader.read_bytes()), 'runtime': observed, 'desktop': desktop_report,
            'commands_tested': len(calls), 'calls': calls, 'all_events_exact_schema_and_private': True,
            'all_available_operations_verified': ['status', 'packages', 'create', 'evidence --text', 'evidence --file',
                                                  'propose', 'check arithmetic', 'check quote', 'check invoice', 'close', 'show', 'list', 'console'],
            'missing_components_fail_closed': ['infer', 'attention', 'packages --verify'],
            'task_actions_executed': 0, 'guest_uid_contract': 'Both processes run as guest UID 0; host checks used matching current UID',
            'not_tested': ['Gio button launch and terminal display in VM', 'Durable task persistence', 'Native model inference']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overlay', type=Path, default=DEFAULT_STAGE / 'overlay-v1')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'build-src/basilisk-stage/overlay-v2')
    parser.add_argument('--reader', type=Path, default=ROOT.parent / 'roko-basilisk/avatar_state.py')
    parser.add_argument('--output', type=Path, default=DEFAULT_STAGE / 'python313-validation-v1.json')
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit('Refusing existing validation receipt')
    report = check(args.overlay.resolve(), args.runtime.resolve(), args.reader.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
