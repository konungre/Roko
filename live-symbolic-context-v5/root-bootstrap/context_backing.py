"""One-shot root bootstrap extension. Default-off caller; no request endpoint."""
import os
from pathlib import Path
import sys
import backing_identity as identity


def capture():
    if (os.getpid()!=1 or os.getresuid()!=(0,0,0) or os.getresgid()!=(0,0,0)
            or Path(__file__).resolve()!=identity.INSTALL/'context_backing.py'
            or Path(identity.__file__).resolve()!=identity.INSTALL/'backing_identity.py'):
        raise ValueError('Existing fixed root PID1 bootstrap required')
    identity.control_directory()
    view=identity.public_view()
    backing={str(path):identity.metadata(path,0,0o700 if path==identity.COW else None)
        for path in (identity.COW,identity.COW/'upper',identity.COW/'work')}
    sources=identity.source_hashes()
    value={'version':1,'purpose':'guest-storage-observation-only','public':view,
        'backing':backing,'sources':sources,'authorizes_actions':False,'executed_actions':0}
    identity.validate(value,view,sources)
    # Catch mount or request-root changes between root inspection and publishing.
    if identity.canonical(identity.public_view())!=identity.canonical(view):
        raise ValueError('Bootstrap identity changed before receipt publication')
    current_backing={str(path):identity.metadata(path,0,0o700 if path==identity.COW else None)
        for path in (identity.COW,identity.COW/'upper',identity.COW/'work')}
    if identity.canonical(current_backing)!=identity.canonical(backing):
        raise ValueError('Bootstrap backing identity changed before publication')
    raw=identity.canonical(value)+b'\n'
    if len(raw)>identity.CAP:raise ValueError('Bootstrap receipt byte cap')
    fd=os.open(identity.RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as stream:
            stream.write(raw);stream.flush();os.fsync(fd)
        os.fchown(fd,0,1000);os.fchmod(fd,0o440);os.fsync(fd)
    finally:os.close(fd)
    directory=os.open(identity.CONTROL,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(directory)
    finally:os.close(directory)
    # Do not remove, rewrite or retry a partial/uncertain receipt on failure.
    observed,_=identity.read_receipt(sources)
    if identity.canonical(observed)!=identity.canonical(value):raise ValueError('Bootstrap receipt readback differs')
    return {'status':'recorded','authorizes_actions':False,'executed_actions':0}
