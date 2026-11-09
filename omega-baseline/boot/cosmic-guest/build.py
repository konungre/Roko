#!/usr/bin/env python3
"""Build a separate hashed COSMIC initramfs. Never starts a VM or executes guest ELF."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import posixpath
from pathlib import Path
import re
import stat
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / 'build-src/cosmic-comp-stage'
OUT = ROOT / 'build/cosmic-guest'
COMMIT = '8cb1802caada438bb5cc7670dfabdaca5fad0502'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def graphics():
    spec = importlib.util.spec_from_file_location('cosmic_graphics', ROOT / 'boot/graphics_probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Closure:
    """Resolve guest paths without ever following an absolute link on the host."""
    def __init__(self, root, lock):
        self.root = root
        self.lock = {x['path']: x for x in lock['files']}
        self.files = {}
        self.sources = {}
        self.elfs = {}

    def resolve(self, path):
        parts = path.lstrip('/').split('/')
        result = []
        links = 0
        while parts:
            part = parts.pop(0)
            if part in ('', '.'):
                continue
            if part == '..':
                if not result:
                    raise ValueError('Guest path escapes root')
                result.pop()
                continue
            trial = '/'.join(result + [part])
            item = self.lock.get(trial)
            actual = self.root / trial
            if actual.is_symlink():
                if not item or item.get('kind') != 'symlink' or str(actual.readlink()) != item['target']:
                    raise ValueError('Unpinned symlink: ' + trial)
                links += 1
                if links > 40:
                    raise ValueError('Symlink loop: ' + path)
                target = item['target']
                if target.startswith('/'):
                    result = []
                parts = target.split('/') + parts
            else:
                result.append(part)
        return '/'.join(result)

    def add(self, path, destination=None):
        key = self.resolve(path)
        rec = self.lock.get(key)
        if not rec or rec.get('kind') != 'file':
            raise ValueError('Required runtime file missing from lock: ' + path)
        source = self.root / key
        data = source.read_bytes()
        if sha(data) != rec['sha256'] or stat.S_IMODE(source.stat().st_mode) != rec['mode']:
            raise ValueError('Runtime source changed: ' + key)
        dest = (destination or path).lstrip('/')
        self.files[dest] = (data, stat.S_IFREG | (rec['mode'] & 0o777))
        self.sources[key] = rec['sha256']
        self.dependencies(source, dest, data)

    def external(self, source, dest):
        if source.is_symlink():
            raise ValueError('Built artifact must be a regular file')
        data = source.read_bytes()
        self.files[dest] = (data, stat.S_IFREG | 0o755)
        self.dependencies(source, dest, data)
        return sha(data)

    def dependencies(self, source, dest, data):
        if not data.startswith(b'\x7fELF') or dest in self.elfs:
            return
        report = subprocess.check_output(['readelf', '-h', '-l', '-d', str(source)], text=True)
        if 'Advanced Micro Devices X86-64' not in report:
            raise ValueError('Non-x86-64 ELF: ' + dest)
        needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', report)
        interp = re.findall(r'Requesting program interpreter: ([^\]]+)', report)
        paths = re.findall(r'\((?:RUNPATH|RPATH)\).*?\[(.*?)\]', report)
        search = []
        for group in paths:
            for directory in group.split(':'):
                directory = directory.replace('${ORIGIN}', '/' + posixpath.dirname(dest)).replace('$ORIGIN', '/' + posixpath.dirname(dest))
                if not directory.startswith('/') or '$' in directory:
                    raise ValueError('Unsupported dynamic search path: ' + directory)
                search.append(directory.lstrip('/'))
        self.elfs[dest] = {'needed': needed, 'interpreter': interp, 'search': search}
        for path in interp:
            if path.lstrip('/') not in self.files:
                self.add(path)
        for name in needed:
            if '/' in name:
                raise ValueError('Non-soname dependency: ' + name)
            candidates = [directory + '/' + name for directory in search] + ['usr/lib/x86_64-linux-gnu/' + name, 'lib/x86_64-linux-gnu/' + name,
                          'usr/lib/' + name, 'lib/' + name]
            for candidate in candidates:
                if self.resolve(candidate) in self.lock:
                    if candidate not in self.files:
                        self.add(candidate)
                    break
            else:
                raise ValueError('Unresolved ELF dependency: ' + name + ' needed by ' + dest)

    def tree(self, prefix):
        items = [p for p, r in self.lock.items() if p.startswith(prefix.rstrip('/') + '/') and r['kind'] in ('file', 'symlink')]
        if not items:
            raise ValueError('Required runtime data tree missing: ' + prefix)
        for p in sorted(items):
            # Package trees selected below contain file symlinks, not directory aliases.
            if self.root.joinpath(self.resolve(p)).is_file():
                self.add(p)


def build(client, compositor):
    g = graphics()
    assets, kernel, busybox, modules, order, graphics_sources = g.inputs()
    source_commit = subprocess.check_output(['git', '-C', str(STAGE / 'source'), 'rev-parse', 'HEAD'], text=True).strip()
    if source_commit != COMMIT:
        raise ValueError('Compositor source HEAD differs from pinned commit')
    lockpath = STAGE / 'debian-files.lock.json'
    lockdata = lockpath.read_bytes()
    c = Closure(STAGE / 'sysroot', json.loads(lockdata))
    binary_hash = c.external(compositor, 'usr/bin/cosmic-comp')
    client_hash = c.external(client, 'usr/bin/roko-wayland-client')
    for path in ['usr/sbin/seatd', 'usr/bin/dbus-daemon', 'usr/bin/udevadm',
                 'usr/lib/systemd/systemd-udevd',
                 'usr/lib/x86_64-linux-gnu/libEGL.so.1',
                 'usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0',
                 'usr/lib/x86_64-linux-gnu/libGLESv2.so.2',
                 'usr/lib/x86_64-linux-gnu/libgbm.so.1',
                 'usr/lib/x86_64-linux-gnu/libwayland-client.so.0',
                 'usr/lib/x86_64-linux-gnu/libwayland-egl.so.1',
                 'usr/lib/x86_64-linux-gnu/libxkbcommon.so.0',
                 'usr/share/glvnd/egl_vendor.d/50_mesa.json']:
        c.add(path)
    for path in ['usr/lib/x86_64-linux-gnu/dri', 'usr/lib/x86_64-linux-gnu/gbm', 'usr/share/libinput', 'usr/share/X11/xkb', 'usr/share/fonts/truetype/dejavu']:
        c.tree(path)
    # Mesa 25 splits gallium into a separately dlopened library on Debian.
    for path in sorted(c.lock):
        if re.fullmatch(r'usr/lib/x86_64-linux-gnu/libgallium-.*\.so', path):
            c.add(path)
    package_lock = json.loads((STAGE / 'debian-packages.lock.json').read_text())
    for package in package_lock['packages']:
        path = 'usr/share/doc/' + package['package'] + '/copyright'
        if c.resolve(path) in c.lock:
            c.add(path)
    files = {name: (data, mode, 0, 0) for name, (data, mode) in c.files.items()}
    def put(name, data, mode=0o444):
        files[name] = (data, stat.S_IFREG | mode, 0, 0)
    put('bin/busybox', busybox, 0o755)
    files['bin/sh'] = (b'busybox', stat.S_IFLNK | 0o777, 0, 0)
    source_data = {}
    for source, dest in [
            ('data/keybindings.ron', 'usr/share/cosmic/com.system76.CosmicSettings.Shortcuts/v1/defaults'),
            ('data/tiling-exceptions.ron', 'usr/share/cosmic/com.system76.CosmicSettings.WindowRules/v1/tiling_exception_defaults')]:
        data = (STAGE / 'source' / source).read_bytes()
        pinned = subprocess.check_output(['git', '-C', str(STAGE / 'source'), 'show', COMMIT + ':' + source])
        if data != pinned:
            raise ValueError('Compositor runtime data differs from pinned commit: ' + source)
        source_data[source] = sha(data)
        put(dest, data)
    scripts = {}
    for source, dest, mode in [('init.sh', 'init', 0o755), ('60-roko-input.rules', 'etc/udev/rules.d/60-roko-input.rules', 0o444),
                                ('session.conf', 'etc/dbus-1/roko-session.conf', 0o444), ('fonts.conf', 'etc/fonts/fonts.conf', 0o444)]:
        data = (HERE / source).read_bytes()
        scripts[source] = sha(data)
        put(dest, data, mode)
    put('etc/passwd', b'root:x:0:0:root:/root:/bin/sh\n')
    put('etc/group', b'root:x:0:\nvideo:x:44:\nrender:x:104:\ninput:x:105:\n')
    put('etc/machine-id', b'77777777777747778777777777777777\n')
    put('etc/module-order', ('\n'.join(order) + '\n').encode())
    put('etc/kernel-release', (kernel + '\n').encode())
    for name, data in modules.items():
        put('modules/' + name + '.ko', data)
    for directory in ['dev', 'proc', 'sys', 'run', 'tmp', 'root', 'etc/udev/rules.d']:
        files[directory] = (b'', stat.S_IFDIR | 0o755, 0, 0)
    files['dev/console'] = (b'', stat.S_IFCHR | 0o600, 5, 1)
    identity = {'compositor_commit': COMMIT, 'compositor_sha256': binary_hash, 'client_sha256': client_hash,
                'runtime_sources': c.sources, 'graphics_sources': graphics_sources, 'scripts': scripts,
                'compositor_runtime_data': source_data}
    build_id = sha(json.dumps(identity, sort_keys=True).encode())
    put('etc/probe-id', (build_id + '\n').encode())
    for name in list(files):
        parent = posixpath.dirname(name)
        while parent:
            files.setdefault(parent, (b'', stat.S_IFDIR | 0o755, 0, 0))
            parent = posixpath.dirname(parent)
    raw = b''.join(g.b.entry(name, data, mode, i + 1, major, minor)
                   for i, (name, (data, mode, major, minor)) in enumerate(sorted(files.items())))
    raw += g.b.entry('TRAILER!!!', b'', 0, len(files) + 1)
    raw += b'\0' * (-len(raw) % 512)
    archive = io.BytesIO()
    with gzip.GzipFile(fileobj=archive, mode='wb', filename='', mtime=0, compresslevel=1) as f:
        f.write(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    data = archive.getvalue()
    (OUT / 'cosmic.cpio.gz').write_bytes(data)
    report = dict(identity, schema=1, build_id=build_id, kernel_release=kernel, elf_closure=c.elfs,
                  runtime_lock_sha256=sha(lockdata), initramfs_sha256=sha(data), initramfs_bytes=len(data),
                  entries=g.b.inspect(raw), boot_tested=False, full_desktop=False, runs_as_root=True, secure_multiuser_os=False,
                  scope='Standalone COSMIC kiosk with one trusted diagnostic client; no Roko actions')
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return {k: report[k] for k in ['build_id', 'initramfs_sha256', 'initramfs_bytes', 'boot_tested']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--compositor', type=Path, default=STAGE / 'target/debug/cosmic-comp')
    args = parser.parse_args()
    print(json.dumps(build(args.client, args.compositor), indent=2))
