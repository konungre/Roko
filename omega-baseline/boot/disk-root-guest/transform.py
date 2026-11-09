"""Exact future root-init transformations; nothing is executed at import."""
def session_init(data):
    mounts=[b'$BB mount -t proc proc /proc || fail proc\n',
            b'$BB mount -t sysfs sysfs /sys || fail sysfs\n',
            b'$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs\n']
    for line in mounts:
        if data.count(line)!=1:raise ValueError('Expected original pseudo-mount hook exactly once')
        data=data.replace(line,b'')
    hook=b'exec </dev/console >/dev/console 2>&1\n'
    if data.count(hook)!=1:raise ValueError('Unexpected console hook')
    data=data.replace(hook,hook+b'echo ROKO_DISK_ROOT_POST_SWITCH\necho ROKO_ROOT_MEMORY_BEGIN\n$BB cat /proc/meminfo\necho ROKO_ROOT_MEMORY_END\n')
    # Existing desktop storage API is retained, but supplied by a root-specific helper.
    if data.count(b'/usr/libexec/roko-storage-mount || fail storage-mount')!=1:
        raise ValueError('Expected storage mount integration')
    old=b'/usr/bin/python3.13 -u /usr/libexec/roko-storage-observe.py >/dev/console 2>&1 &\nstorage_observer_pid=$!'
    if data.count(old)!=1:raise ValueError('Expected storage observer integration')
    new=(b'if $BB grep -q " roko.root-data=read\\| roko.root-data=write" /proc/cmdline; then\n'
         b'    /usr/bin/python3.13 -u /usr/libexec/roko-storage-observe.py >/dev/console 2>&1 &\n'
         b'    storage_observer_pid=$!\nfi')
    return data.replace(old,new)
