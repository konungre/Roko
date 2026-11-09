"""Actual non-root private128MiB request tmpfs, not ISO004's root COW."""
import os
import context_policy
import backing_identity as identity

GUEST_WORK_FREE_FLOOR=identity.FLOOR
NATIVE_REQUEST_CAP=32


def _report(target):
    receipt,digest=identity.read_receipt(context_policy.BOOTSTRAP_SOURCES)
    if target==identity.WORK:
        work=identity.metadata(target,1000,0o700)
        identity.require(work['device']==receipt['public']['request_root']['device'],
            'Native work directory is not on the admitted private request tmpfs')
    fs=os.statvfs(target);total=fs.f_blocks*fs.f_frsize;free=fs.f_bavail*fs.f_frsize
    identity.require(total==identity.TOTAL,'Private request tmpfs capacity differs')
    identity.require(free>=GUEST_WORK_FREE_FLOOR,'32MiB private request tmpfs free-space floor')
    return {'work_path':str(identity.WORK),'statvfs_path':str(target),
        'request_mount':str(identity.REQUEST),'filesystem':'private128MiB-tmpfs',
        'device':receipt['public']['request_root']['device'],'total_bytes':total,
        'free_bytes':free,'floor_bytes':GUEST_WORK_FREE_FLOOR,
        'bootstrap_receipt_sha256':digest,'boot_id':receipt['public']['boot_id'],
        'mount_namespace':receipt['public']['mount_namespace'],'authorizes_actions':False}


def admit_request():
    # This fixed existing mount root is available before any per-request dirs or
    # lock/state/receipt files are created. No cwd fallback or directory write.
    return _report(identity.REQUEST)


def checked_free():
    # The native working directory is created only after admit_request succeeds.
    # Each child separately rechecks its exact fixed filesystem before startup.
    return _report(identity.WORK)
