"""Source-only identity/config policy. No process, privilege, or device changes."""
import re
import stat

UID = GID = 1000
HOME = '/home/roko'
RUNTIME = '/run/user/1000'
STATE = '/var/lib/roko/live-requests'
CAP_FIELDS = ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')
COMMANDS = {
    'dbus': ('/usr/bin/dbus-daemon', '--config-file=/etc/dbus-1/roko-session.conf', '--nofork'),
    'pipewire': ('/usr/bin/pipewire',),
    'wireplumber': ('/usr/bin/wireplumber',),
    'session': ('/usr/bin/cosmic-session', 'cosmic-comp', '--no-xwayland'),
    'basilisk': ('/usr/bin/roko-companion',),
}


def environment(role, display=None):
    if role not in COMMANDS:
        raise ValueError('Fixed desktop role required')
    if role == 'basilisk':
        if not isinstance(display, str) or re.fullmatch(r'wayland-[0-9]{1,3}', display) is None:
            raise ValueError('Fixed runtime Wayland socket name required')
    elif display is not None:
        raise ValueError('Only the companion takes a Wayland display')
    env = dict(PATH='/usr/bin:/bin:/usr/sbin', HOME=HOME, USER='roko', LOGNAME='roko',
        XDG_RUNTIME_DIR=RUNTIME, XDG_CONFIG_HOME=HOME+'/.config', XDG_CACHE_HOME=HOME+'/.cache',
        XDG_STATE_HOME=HOME+'/.local/state', XDG_DATA_HOME=HOME+'/.local/share',
        XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='COSMIC', XDG_SESSION_DESKTOP='COSMIC',
        XDG_DATA_DIRS='/usr/share', XDG_CONFIG_DIRS='/etc/roko-showcase-xdg:/etc',
        SHELL='/bin/sh', TERM='xterm-256color', LANGUAGE='en_US:en', LANG='C.UTF-8', LC_ALL='C.UTF-8',
        XKB_CONFIG_ROOT='/usr/share/X11/xkb', FONTCONFIG_FILE='/etc/fonts/fonts.conf',
        LIBSEAT_BACKEND='seatd', SEATD_SOCK='/run/seatd.sock', SEATD_VTBOUND='0',
        LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='2',
        LIBGL_DRIVERS_PATH='/usr/lib/x86_64-linux-gnu/dri',
        __EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/50_mesa.json',
        COSMIC_BACKEND='kms', WGPU_BACKEND='gl', GDK_BACKEND='wayland', RUST_LOG='warn',
        DBUS_SESSION_BUS_ADDRESS='unix:path='+RUNTIME+'/bus',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    if display is not None:
        env['WAYLAND_DISPLAY'] = display
    return env


def directory_metadata(info, *, owner, mode=None):
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_gid != (0 if owner == 0 else GID)
            or info.st_mode & 0o022 or (mode is not None and stat.S_IMODE(info.st_mode) != mode)):
        raise ValueError('Unexpected directory type, owner, group or permissions')


def private_file_metadata(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != UID or info.st_gid != GID
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError('Private single-link UID1000:GID1000 mode0600 file required')


def status_fields(text):
    if not isinstance(text, str) or len(text) > 65536:
        raise ValueError('Bounded process status required')
    rows = {}
    for line in text.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key in rows:
            raise ValueError('Duplicate status field')
        rows[key] = value.split()
    return rows


def verify_status(text):
    rows = status_fields(text)
    if rows.get('Uid') != [str(UID)]*4 or rows.get('Gid') != [str(GID)]*4 or rows.get('Groups') != []:
        raise ValueError('Exact real/effective/saved/fs identity and empty supplementary groups required')
    for key in CAP_FIELDS:
        value = rows.get(key)
        if not value or len(value) != 1 or re.fullmatch('[0-9a-fA-F]{1,16}', value[0]) is None or int(value[0], 16):
            raise ValueError('Every capability set must be zero: '+key)
    if rows.get('NoNewPrivs') != ['1']:
        raise ValueError('NoNewPrivs must be set')
    return True


def drop_steps(last_cap):
    if type(last_cap) is not int or not 0 <= last_cap <= 63:
        raise ValueError('Unsupported Linux capability range')
    # Clear ambient and the bounding set while CAP_SETPCAP is still available.
    # setresgid/setresuid clear all saved identities, not just effective IDs.
    return [('prctl', 38, 1), ('prctl', 8, 0), ('prctl', 47, 4),
            *[('prctl', 24, cap) for cap in range(last_cap+1)],
            ('setgroups', ()), ('setresgid', GID, GID, GID),
            ('setresuid', UID, UID, UID), ('capset_zero',), ('verify_status',)]


def apply_drop(backend, last_cap):
    """Backend-injected sequence; tests use only a recorder, never Linux calls."""
    for operation, *args in drop_steps(last_cap):
        getattr(backend, operation)(*args)


def readonly_mount(raw, point, *, mutable_trees=()):
    if type(raw) is not str or len(raw) > 1048576:
        raise ValueError('Bounded mountinfo required')
    matches = []
    for line in raw.splitlines():
        row = line.split()
        if len(row) < 10 or row.count('-') != 1:
            raise ValueError('Invalid mountinfo')
        split = row.index('-')
        if split < 6 or len(row) != split+4:
            raise ValueError('Invalid mountinfo fields')
        mountpoint = re.sub(r'\\(040|011|012|134)', lambda m: chr(int(m[1], 8)), row[4])
        if mountpoint == point:
            matches.append(row)
        elif mountpoint.startswith(point.rstrip('/') + '/'):
            # Deny even readonly hidden submounts within protected trees. They
            # can replace pinned root code. Root has explicit runtime exceptions.
            if not any(mountpoint == tree or mountpoint.startswith(tree + '/') for tree in mutable_trees):
                raise ValueError('Unexpected mount hides protected input tree')
    if len(matches) != 1:
        raise ValueError('Exactly one fixed mount required')
    row = matches[0]
    if 'ro' not in row[5].split(',') or 'rw' in row[5].split(','):
        raise ValueError('Mount must be read-only')
    # A bind may have rw backing tmpfs while its own VFS mount is ro.
    return True
