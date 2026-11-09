#!/usr/bin/env python3
"""Separate genuine reduced desktop image. --check never builds or boots."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import stat
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / 'build-src/cosmic-desktop-stage'
OUT = ROOT / 'build/cosmic-session-guest'
TERMDATA = ROOT / 'build-src/cosmic-termdata-stage'
COMPONENTS = ['cosmic-session', 'cosmic-settings-daemon', 'cosmic-notifications',
              'cosmic-panel', 'cosmic-applets', 'cosmic-bg', 'cosmic-app-library',
              'cosmic-term', 'pop-launcher', 'cosmic-launcher']
BINARY_NAMES = {x: x for x in COMPONENTS}
BINARY_NAMES['pop-launcher'] = 'pop-launcher-bin'
APPLETS = {'cosmic-app-list': 'com.system76.CosmicAppList',
           'cosmic-applet-minimize': 'com.system76.CosmicAppletMinimize',
           'cosmic-applet-notifications': 'com.system76.CosmicAppletNotifications',
           'cosmic-applet-tiling': 'com.system76.CosmicAppletTiling',
           'cosmic-applet-time': 'com.system76.CosmicAppletTime',
           'cosmic-panel-app-button': 'com.system76.CosmicPanelAppButton',
           'cosmic-panel-launcher-button': 'com.system76.CosmicPanelLauncherButton'}

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

base = module('immutable_cosmic_guest_build', ROOT / 'boot/cosmic-guest/build.py')

class Assets:
    def __init__(self):
        self.records = []
        self.blockers = []
        self.dependency_commits = {}
        self.source_lock = json.loads((STAGE / 'sources.lock.json').read_text())
        self.commits = {x['component']: x['commit'] for x in self.source_lock['components']}

    def file(self, source, destination, component=None, generated=False, mode=0o444):
        source = Path(source)
        allowed = STAGE / 'sources' / component if component else ROOT
        try:
            source.resolve().relative_to(allowed.resolve())
        except ValueError:
            self.blockers.append('Source asset link escapes component: ' + str(source))
            return
        if not source.is_file():
            self.blockers.append('Missing data: ' + str(source.relative_to(ROOT)))
            return
        self.records.append({'source': str(source.relative_to(ROOT)), 'destination': destination,
                             'component': component, 'generated': generated, 'mode': mode})

    def tree(self, path, destination, component):
        if not path.is_dir():
            self.blockers.append('Missing data tree: ' + str(path.relative_to(ROOT)))
            return
        for source in sorted(path.rglob('*')):
            if source.is_file():
                self.file(source, destination + '/' + str(source.relative_to(path)), component)

    def desktop(self, component, appid, fallback=None):
        source = STAGE / 'sources' / component
        generated = source / 'target/xdgen' / (appid + '.desktop')
        if generated.is_file():
            self.file(generated, 'usr/share/applications/' + generated.name, component, True)
        else:
            path = source / (fallback or ('data/' + appid + '.desktop'))
            self.file(path, 'usr/share/applications/' + path.name, component)

    def collect(self):
        if not (TERMDATA / 'debian-files.lock.json').is_file():
            self.blockers.append('Missing signed terminfo file lock')
        for component in COMPONENTS:
            receipt = STAGE / 'artifacts' / (component + '.json')
            if not receipt.is_file():
                self.blockers.append('Missing build receipt: ' + component)
                continue
            record = json.loads(receipt.read_text())
            if record.get('exit_code') != 0 or record.get('source_commit') != self.commits[component]:
                self.blockers.append('Invalid build receipt: ' + component)
            binary = BINARY_NAMES[component]
            found = next((x for x in record['artifacts'] if x['binary'] == binary), None)
            if not found:
                self.blockers.append('Missing artifact: ' + binary)
                continue
            self.records.append(dict(found, source=found['path'], destination='usr/bin/' + component,
                                     component=component, generated=True, mode=0o755, binary=True))
        for name, appid in [('cosmic-app-library', 'com.system76.CosmicAppLibrary'),
                            ('cosmic-launcher', 'com.system76.CosmicLauncher')]:
            self.desktop(name, appid)
            self.file(STAGE / f'sources/{name}/data/icons/{appid}.svg', f'usr/share/icons/hicolor/scalable/apps/{appid}.svg', name)
        self.desktop('cosmic-term', 'com.system76.CosmicTerm')
        self.tree(STAGE / 'sources/cosmic-term/res/icons/hicolor', 'usr/share/icons/hicolor', 'cosmic-term')
        self.tree(STAGE / 'sources/cosmic-panel/data/default_schema', 'usr/share/cosmic', 'cosmic-panel')
        self.tree(STAGE / 'sources/cosmic-bg/data/v1', 'usr/share/cosmic/com.system76.CosmicBackground/v1', 'cosmic-bg')
        self.file(STAGE / 'sources/cosmic-settings-daemon/data/system_actions.ron',
                  'usr/share/cosmic/com.system76.CosmicSettings.Shortcuts/v1/system_actions', 'cosmic-settings-daemon')
        for name, appid in APPLETS.items():
            self.desktop('cosmic-applets', appid, name + '/data/' + appid + '.desktop')
            self.tree(STAGE / 'sources/cosmic-applets' / name / 'data/icons', 'usr/share/icons/hicolor', 'cosmic-applets')
            schema = STAGE / 'sources/cosmic-applets' / name / 'data/default_schema'
            if schema.is_dir():
                self.tree(schema, 'usr/share/cosmic', 'cosmic-applets')
        for plugin in ['desktop_entries', 'cosmic_toplevel', 'terminal']:
            self.tree(STAGE / 'sources/pop-launcher/plugins/src' / plugin, 'usr/lib/pop-launcher/plugins/' + plugin, 'pop-launcher')
            # Only the upstream .ron manifests are installed, never plugin Rust source.
            self.records = [r for r in self.records if not r['destination'].startswith('usr/lib/pop-launcher/') or r['destination'].endswith('.ron')]
        for prefix in ['freedesktop', 'extra']:
            self.tree(STAGE / 'sources/cosmic-icons' / prefix / 'scalable', 'usr/share/icons/Cosmic/scalable', 'cosmic-icons')
        self.file(STAGE / 'sources/cosmic-icons/index.theme', 'usr/share/icons/Cosmic/index.theme', 'cosmic-icons')
        # RustEmbed's debug implementation reads the absolute Cargo manifest
        # i18n path. Preserve those real assets in this disposable prototype.
        for component in COMPONENTS:
            source_root = STAGE / 'sources' / component
            for folder in sorted(source_root.rglob('i18n')):
                if folder.is_dir() and 'target' not in folder.relative_to(source_root).parts:
                    self.tree(folder, str(folder).lstrip('/'), component)
        dependency_lock = json.loads((STAGE / 'dependency-sources.lock.json').read_text())
        for path, record in dependency_lock['git_checkouts'].items():
            root = ROOT / path
            if root.parent.name.startswith('libcosmic-') and (root / 'i18n').is_dir():
                head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
                if head != record['commit']:
                    self.blockers.append('Wrong localization dependency commit: ' + path)
                    continue
                subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--', 'i18n'], check=True)
                self.dependency_commits[path] = head
                self.tree(root / 'i18n', str(root / 'i18n').lstrip('/'), None)
        for component in COMPONENTS + ['cosmic-icons']:
            for source in sorted((STAGE / 'sources' / component).iterdir()):
                if source.is_file() and source.name.upper().startswith(('LICENSE', 'COPYING')):
                    self.file(source, 'usr/share/doc/' + component + '/' + source.name, component)
        return self


def build(assets):
    if assets.blockers:
        raise ValueError('; '.join(assets.blockers))
    g = base.graphics()
    _, kernel, busybox, modules, order, graphics_sources = g.inputs()
    lockdata = (STAGE / 'debian-files.lock.json').read_bytes()
    closure = base.Closure(STAGE / 'sysroot', json.loads(lockdata))
    provenance = []
    for component, commit in assets.commits.items():
        source = STAGE / 'sources' / component
        head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if head != commit:
            raise ValueError('Wrong source commit: ' + component)
        subprocess.run(['git', '-C', str(source), 'diff', '--quiet', 'HEAD'], check=True)
    for record in assets.records:
        source = ROOT / record['source']
        data = source.read_bytes()
        if record.get('sha256') and base.sha(data) != record['sha256']:
            raise ValueError('Built binary changed: ' + str(source))
        if record.get('binary'):
            closure.external(source, record['destination'])
        else:
            closure.files[record['destination']] = (data, stat.S_IFREG | record['mode'])
        provenance.append(dict(record, sha256=base.sha(data), bytes=len(data)))
    # Independently proven unchanged compositor; separate instrumented session client.
    prior = json.loads((ROOT / 'build/cosmic-guest/manifest.json').read_text())
    for source, destination, expected in [
            (base.STAGE / 'target/debug/cosmic-comp', 'usr/bin/cosmic-comp', prior['compositor_sha256']),
            (ROOT / 'desktop/session-wayland-test-client/build/roko-session-wayland-test', 'usr/bin/roko-wayland-client', 'e4cb2b9dca728559a99e8283d9b88b9f8009d527bde887d4423453e1f9187014')]:
        if closure.external(source, destination) != expected:
            raise ValueError('Proven artifact changed: ' + str(source))
    for path in ['usr/sbin/seatd', 'usr/bin/dbus-daemon', 'usr/bin/dbus-send', 'usr/bin/udevadm',
                 'usr/lib/systemd/systemd-udevd', 'usr/bin/pipewire', 'usr/bin/wireplumber',
                 'usr/lib/x86_64-linux-gnu/libEGL.so.1', 'usr/lib/x86_64-linux-gnu/libGL.so.1',
                 'usr/lib/x86_64-linux-gnu/libGLX_mesa.so.0', 'usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0',
                 'usr/lib/x86_64-linux-gnu/libGLESv2.so.2', 'usr/lib/x86_64-linux-gnu/libgbm.so.1',
                 'usr/lib/x86_64-linux-gnu/libwayland-client.so.0', 'usr/lib/x86_64-linux-gnu/libwayland-egl.so.1',
                 'usr/lib/x86_64-linux-gnu/libxkbcommon.so.0', 'usr/share/glvnd/egl_vendor.d/50_mesa.json']:
        closure.add(path)
    for path in ['usr/lib/x86_64-linux-gnu/dri', 'usr/lib/x86_64-linux-gnu/gbm',
                 'usr/lib/x86_64-linux-gnu/pipewire-0.3', 'usr/lib/x86_64-linux-gnu/spa-0.2',
                 'usr/share/pipewire', 'usr/share/wireplumber', 'usr/share/libinput',
                 'usr/share/X11/xkb', 'usr/share/X11/locale', 'usr/share/fonts/truetype/dejavu']:
        closure.tree(path)
    if any(p.startswith('usr/lib/locale/C.utf8/') for p in closure.lock):
        closure.tree('usr/lib/locale/C.utf8')
    for path in sorted(closure.lock):
        if path.startswith('usr/lib/x86_64-linux-gnu/libgallium-') and path.endswith('.so'):
            closure.add(path)
        if path.startswith('usr/lib/x86_64-linux-gnu/wireplumber-'):
            closure.add(path)
        if path.startswith(('usr/lib/terminfo/', 'usr/share/terminfo/', 'lib/terminfo/')) and path.endswith(('/xterm', '/xterm-256color')):
            closure.add(path)
    for package in json.loads((STAGE / 'debian-packages.lock.json').read_text())['packages']:
        path = 'usr/share/doc/' + package['package'] + '/copyright'
        if closure.resolve(path) in closure.lock:
            closure.add(path)
    term_lock = (TERMDATA / 'debian-files.lock.json').read_bytes()
    term = base.Closure(TERMDATA / 'sysroot', json.loads(term_lock))
    term.tree('etc/terminfo')
    term.tree('usr/share/terminfo')
    for package in ['ncurses-base', 'ncurses-term']:
        path = 'usr/share/doc/' + package + '/copyright'
        if term.resolve(path) in term.lock:
            term.add(path)
    if 'usr/share/terminfo/x/xterm-256color' not in term.files and 'etc/terminfo/x/xterm-256color' not in term.files:
        raise ValueError('Real xterm-256color terminfo missing')
    for name, entry in term.files.items():
        if name in closure.files and closure.files[name] != entry:
            raise ValueError('Conflicting terminfo path: ' + name)
        closure.files[name] = entry
    files = {name: (data, mode, 0, 0) for name, (data, mode) in closure.files.items()}
    def put(name, data, mode=0o444):
        files[name] = (data, stat.S_IFREG | mode, 0, 0)
    def link(name, target):
        files[name] = (target.encode(), stat.S_IFLNK | 0o777, 0, 0)
    for name in APPLETS:
        if not name.startswith('cosmic-panel-'):
            link('usr/bin/' + name, 'cosmic-applets')
    link('usr/bin/cosmic-panel-button', 'cosmic-applets')
    for plugin in ['desktop_entries', 'cosmic_toplevel', 'terminal']:
        link('usr/lib/pop-launcher/plugins/' + plugin + '/' + plugin.replace('_', '-'), '/usr/bin/pop-launcher')
    scripts = {}
    for source, dest, mode in [
            ('init.sh', 'init', 0o755), ('60-roko-input.rules', 'etc/udev/rules.d/60-roko-input.rules', 0o444),
            ('session.conf', 'etc/dbus-1/roko-session.conf', 0o444), ('fonts.conf', 'etc/fonts/fonts.conf', 0o444),
            ('roko-session-test.sh', 'usr/bin/roko-session-test', 0o755),
            ('roko-terminal-shell.sh', 'usr/bin/roko-terminal-shell', 0o755),
            ('roko-terminal-launch.sh', 'usr/bin/roko-terminal-launch', 0o755),
            ('com.roko.Terminal.desktop', 'usr/share/applications/com.roko.Terminal.desktop', 0o444),
            ('roko-terminal-check.sh', 'usr/bin/roko-terminal-check', 0o755),
            ('roko-session-finish.sh', 'usr/bin/roko-session-finish', 0o755),
            ('com.roko.GraphicsTest.desktop', 'usr/share/applications/com.roko.GraphicsTest.desktop', 0o444),
            ('background.ron', 'root/.config/cosmic/com.system76.CosmicBackground/v1/all', 0o444),
            ('panel-wings.ron', 'root/.config/cosmic/com.system76.CosmicPanel.Panel/v1/plugins_wings', 0o444),
            ('dock-center.ron', 'root/.config/cosmic/com.system76.CosmicPanel.Dock/v1/plugins_center', 0o444)]:
        data = (HERE / source).read_bytes()
        scripts[source] = base.sha(data)
        put(dest, data, mode)
    for source, dest in [
            ('data/keybindings.ron', 'usr/share/cosmic/com.system76.CosmicSettings.Shortcuts/v1/defaults'),
            ('data/tiling-exceptions.ron', 'usr/share/cosmic/com.system76.CosmicSettings.WindowRules/v1/tiling_exception_defaults')]:
        data = (base.STAGE / 'source' / source).read_bytes()
        if base.sha(data) != prior['compositor_runtime_data'][source]:
            raise ValueError('Proven compositor data changed')
        put(dest, data)
    put('bin/busybox', busybox, 0o755)
    link('bin/sh', 'busybox')
    # The real terminal's shell gets ordinary commands, not a fake command responder.
    for applet in ['cat', 'echo', 'printf', 'ls', 'pwd', 'uname', 'sleep', 'env', 'clear', 'true', 'false',
                   'mkdir', 'rmdir', 'cp', 'mv', 'rm', 'touch', 'date', 'grep', 'sed', 'awk', 'head', 'tail',
                   'wc', 'cut', 'sort', 'uniq', 'find', 'xargs', 'basename', 'dirname', 'readlink', 'which',
                   'id', 'whoami', 'ps', 'kill', 'df', 'du', 'free', 'uptime', 'test', 'stty', 'reset']:
        # Never hide a staged real executable with an applet link earlier in PATH.
        if 'bin/' + applet not in files and 'usr/bin/' + applet not in files:
            link('bin/' + applet, 'busybox')
    put('etc/passwd', b'root:x:0:0:root:/root:/bin/sh\n')
    put('etc/group', b'root:x:0:\nvideo:x:44:\nrender:x:104:\ninput:x:105:\n')
    put('etc/machine-id', b'77777777777747778777777777777777\n')
    put('etc/module-order', ('\n'.join(order) + '\n').encode())
    put('etc/kernel-release', (kernel + '\n').encode())
    for name, data in modules.items():
        put('modules/' + name + '.ko', data)
    for directory in ['dev', 'proc', 'sys', 'run', 'tmp', 'root/.cache']:
        files[directory] = (b'', stat.S_IFDIR | 0o755, 0, 0)
    files['dev/console'] = (b'', stat.S_IFCHR | 0o600, 5, 1)
    identity = {'component_assets': provenance, 'source_commits': assets.commits, 'localization_dependency_commits': assets.dependency_commits,
                'debug_runtime_source_paths_included': True,
                'runtime_sources': closure.sources, 'graphics_sources': graphics_sources,
                'terminfo_sources': term.sources, 'terminfo_lock_sha256': base.sha(term_lock),
                'scripts': scripts, 'kernel_release': kernel,
                'proven_compositor_sha256': prior['compositor_sha256'], 'client_sha256': 'e4cb2b9dca728559a99e8283d9b88b9f8009d527bde887d4423453e1f9187014', 'original_client_sha256': prior['client_sha256'], 'session_client_sources': {p: base.sha((ROOT / 'desktop/session-wayland-test-client' / p).read_bytes()) for p in ['main.c', 'pattern.h', 'build.sh', 'verify_capture.py']}}
    build_id = base.sha(json.dumps(identity, sort_keys=True).encode())
    put('etc/probe-id', (build_id + '\n').encode())
    for name in list(files):
        for parent in Path(name).parents:
            if str(parent) != '.':
                files.setdefault(str(parent), (b'', stat.S_IFDIR | 0o755, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'session.cpio.gz'
    # Stream archive to avoid duplicating the full multi-binary image in RAM.
    with archive.open('wb') as raw_output:
        with gzip.GzipFile(fileobj=raw_output, mode='wb', filename='', mtime=0, compresslevel=1) as output:
            length = 0
            for i, (name, (data, mode, major, minor)) in enumerate(sorted(files.items())):
                entry = g.b.entry(name, data, mode, i + 1, major, minor)
                output.write(entry)
                length += len(entry)
            trailer = g.b.entry('TRAILER!!!', b'', 0, len(files) + 1)
            output.write(trailer)
            output.write(b'\0' * (-(length + len(trailer)) % 512))
    entries = {name: {'mode': mode, 'bytes': len(data), 'sha256': base.sha(data), 'uid': 0, 'gid': 0, 'mtime': 0,
                      'rdevmajor': major, 'rdevminor': minor}
               for name, (data, mode, major, minor) in files.items()}
    report = dict(identity, schema=1, build_id=build_id, elf_closure=closure.elfs, entries=entries,
                  runtime_lock_sha256=base.sha(lockdata), initramfs_sha256=base.sha(archive.read_bytes()),
                  initramfs_bytes=archive.stat().st_size, uncompressed_file_bytes=sum(len(v[0]) for v in files.values()),
                  boot_tested=False, full_desktop=False, runs_as_root=True, secure_multiuser_os=False,
                  scope='Genuine reduced COSMIC session; no Roko model/controller/autonomy')
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return {k: report[k] for k in ['build_id', 'initramfs_bytes', 'uncompressed_file_bytes', 'boot_tested']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assets = Assets().collect()
    if args.build:
        print(json.dumps(build(assets), indent=2))
    else:
        print(json.dumps({'boot_tested': False, 'asset_count': len(assets.records), 'blockers': assets.blockers}, indent=2))
        raise SystemExit(2 if assets.blockers else 0)
