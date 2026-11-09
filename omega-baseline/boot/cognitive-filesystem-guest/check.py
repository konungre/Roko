"""Exercise the genuine Roko CLI and StateStore; synthetic evidence, actual stored state."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

CLI=Path('/opt/roko/scripts/roko.py')
DIRECTORY=Path('/data/roko-state')
RECEIPT=Path('/data/verification.json')
TASK='ext4-controller-arithmetic'
PENDING='ext4-controller-pending'
GOAL='Recover a verified Roko controller task from mounted ext4 after reboot'

def call(*args,expected=0):
    result=subprocess.run([sys.executable,str(CLI),'--state-dir',str(DIRECTORY),*args],capture_output=True,text=True,timeout=20)
    if result.returncode!=expected:
        raise RuntimeError('CLI unexpected exit: '+repr(args)+' '+str(result.returncode)+' '+result.stdout+' '+result.stderr)
    return result.stdout

def metadata(path,mode,directory=False):
    s=path.lstat()
    if path.is_symlink() or stat.S_IMODE(s.st_mode)!=mode or s.st_uid!=os.getuid() or (not directory and s.st_nlink!=1):
        raise ValueError('Unsafe controller file metadata: '+str(path))
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):
        raise ValueError('Unexpected controller file type')

def snapshot():
    sys.path.insert(0,str(CLI.parents[1]/'adapters'))
    from state_store import StateStore
    store=StateStore(DIRECTORY)
    result={}
    for task,revision in [(TASK,7),(PENDING,2)]:
        shown=json.loads(call('show',task))
        state,actual=store.load(task)
        if actual!=revision or shown!={'revision':actual,'state':state.snapshot()}:
            raise ValueError('CLI/StateStore recovery disagrees')
        if shown['state']['executed_actions']!=0:
            raise ValueError('Unexpected action assertion')
        result[task]=shown
    final=result[TASK]['state']
    if final['phase']!='closed' or final['goal']!=GOAL or final['proposal']['arguments']!={'text':'56'}:
        raise ValueError('Wrong recovered completed task')
    if final['verification']['authorizes_actions'] is not False or final['verification']['accepted'] is not True:
        raise ValueError('Wrong recovered checker result')
    if final['evidence']['source']['text']!='Arithmetic: 7 * 8.':
        raise ValueError('Wrong recovered evidence')
    pending=result[PENDING]['state']
    if pending['phase']!='open' or pending['proposal'] is not None or pending['verification'] is not None:
        raise ValueError('Pending task was not preserved')
    listed=json.loads(call('list'))
    if {x['task']:x['revision'] for x in listed}!={TASK:7,PENDING:2}:
        raise ValueError('Unexpected task listing')
    metadata(DIRECTORY,0o700,True)
    for path in DIRECTORY.iterdir(): metadata(path,0o600)
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DIRECTORY.glob('*.json'))}
    if len(files)!=2 or len(list(DIRECTORY.iterdir()))!=4:
        raise ValueError('Unexpected controller files or temp-file leak')
    return {'states':result,'checkpoint_sha256':files}

def run(phase):
    os.umask(0o077)
    if phase=='write':
        DIRECTORY.mkdir(mode=0o700)  # Existing task directory is never overwritten.
        fd=os.open(DIRECTORY.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        call('create',TASK,'--goal',GOAL)
        call('create',TASK,'--goal',GOAL,expected=3)
        call('evidence',TASK,'source','--source','fixture:ext4-controller','--text','Arithmetic: 7 * 8.')
        call('propose',TASK,'--tool','record_answer','--arguments','{"text":"55"}','--evidence','source')
        call('check',TASK,'--checker','arithmetic')
        call('close',TASK,expected=2)
        rejected=json.loads(call('show',TASK))
        if rejected['revision']!=4 or rejected['state']['phase']!='open' or rejected['state']['verification']['accepted']:
            raise ValueError('Incorrect proposal was not rejected')
        print('ROKO_EXT4_CONTROLLER_REJECTION_PASSED',flush=True)
        call('propose',TASK,'--tool','record_answer','--arguments','{"text":"56"}','--evidence','source')
        call('check',TASK,'--checker','arithmetic')
        call('close',TASK)
        call('create',PENDING,'--goal','Keep an unverified task open across reboot')
        call('evidence',PENDING,'source','--source','fixture:ext4-pending','--text','No action is authorized.')
        data=snapshot()
        fd=os.open(RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream,sort_keys=True); stream.flush(); os.fsync(stream.fileno())
        fd=os.open(RECEIPT.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    elif phase=='read':
        metadata(RECEIPT,0o600)
        expected=json.loads(RECEIPT.read_text())
        data=snapshot()
        if expected!=data:
            raise ValueError('Checkpoint content/revision changed across boot')
    else: raise ValueError('Expected write/read')
    print('ROKO_EXT4_CONTROLLER_STATE '+json.dumps(data,sort_keys=True),flush=True)
    print('ROKO_EXT4_CONTROLLER_'+phase.upper()+'_PASSED tasks=2 revisions=7,2 actions=0',flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Expected one phase')
    run(sys.argv[1])
