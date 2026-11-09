"""Fixed-image lifetime/attachment API for a separate COSMIC runner. Never launches QEMU."""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'build/desktop-filesystem-guest'
def module(name):
    spec=importlib.util.spec_from_file_location('desktop_storage_'+name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value
image=module('image')
formatter=module('formatter')

def create():
    formatter.verify()
    fd=image.open_image(ROOT,create=True)
    try:
        provenance,output=formatter.execute('mke2fs',fd,format_image=True); os.fsync(fd)
        _,check=formatter.execute('e2fsck',fd)
        _,header=formatter.execute('dumpe2fs',fd)
        report=dict(provenance,formatted=True,filesystem_checked=True,formatter_output=output,fsck_output=check,superblock=header)
        receipt=os.open(OUT/'format-receipt.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(receipt,'w') as stream:
            json.dump(report,stream,indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        return report
    finally: os.close(fd)

@contextmanager
def admitted():
    fd=image.open_image(ROOT)
    try:
        if os.pread(fd,2,1080)!=b'\x53\xef' or os.pread(fd,16,1128)!=uuid.UUID(image.UUID).bytes:
            raise ValueError('Wrong desktop image filesystem identity')
        yield fd
    finally: os.close(fd)

def attach_command(command,fd,phase):
    if phase not in ('write','read'): raise ValueError('Expected explicit write/read phase')
    forbidden={'-blockdev','-drive','-hda','-hdb','-hdc','-hdd','-fda','-fdb','-cdrom','-virtfs','-fsdev'}
    if forbidden.intersection(command): raise ValueError('Existing disk/share arguments not permitted')
    if command.count('-append')!=1 or '-nic' not in command or command[command.index('-nic')+1]!='none':
        raise ValueError('Expected network-disabled guest command')
    result=list(command)
    pos=result.index('-append')+1
    if 'roko.desktop-storage=' in result[pos]: raise ValueError('Storage phase already supplied')
    result[pos]+=' roko.desktop-storage='+phase
    result+=image.attach(fd)
    return result

def fsck(fd):
    provenance,log=formatter.execute('e2fsck',fd)
    return {'passed':True,'provenance':provenance,'log':log}

def validate_pair(write_log,read_log):
    """Storage evidence only: GUI runner must separately prove desktop interaction/lifecycle."""
    snapshots=[]
    for phase,log in [('write',write_log),('read',read_log)]:
        lines=log.splitlines()
        required=['ROKO_DESKTOP_STORAGE_MOUNTED '+phase,'ROKO_DESKTOP_STORAGE_'+phase.upper()+'_PASSED','ROKO_DESKTOP_STORAGE_UNMOUNTED']
        if phase=='write': required.append('ROKO_DESKTOP_STORAGE_BLANK')
        if not all(x in lines for x in required) or 'ROKO_DESKTOP_STORAGE_FAILED' in log:
            raise ValueError('Missing/failing '+phase+' storage markers')
        values=[json.loads(x.removeprefix('ROKO_DESKTOP_STORAGE_STATE ')) for x in lines if x.startswith('ROKO_DESKTOP_STORAGE_STATE ')]
        if len(values)!=1: raise ValueError('Expected one actual checkpoint snapshot per boot')
        if phase=='write':
            consoles=[json.loads(x.removeprefix('ROKO_DESKTOP_STORAGE_CONSOLES ')) for x in lines if x.startswith('ROKO_DESKTOP_STORAGE_CONSOLES ')]
            if len(consoles)!=1: raise ValueError('Missing console process record')
            def genuine(record):
                args=record.get('argv',[])
                return (type(record.get('pid')) is int and record['pid']>0 and '/opt/roko/scripts/roko.py' in args and args[-1:]==['console']
                        and '--state-dir' in args and args[args.index('--state-dir')+1:args.index('--state-dir')+2]==['/var/lib/roko']
                        and '--avatar-events' in args and args[args.index('--avatar-events')+1:args.index('--avatar-events')+2]==['/run/user/0/roko/avatar.json'])
            if not any(genuine(record) for record in consoles[0]): raise ValueError('No actual persistent desktop console process observed')
        snapshots.append(values[0])
    if snapshots[0]!=snapshots[1]: raise ValueError('Checkpoint changed across desktop boot')
    value=snapshots[0]
    if value['task']!='desktop-persist' or value['revision']!=5 or value['state']['phase']!='closed' or value['state']['executed_actions']!=0:
        raise ValueError('Unexpected checkpoint state')
    return {'storage_passed':True,'snapshot':value,'desktop_input_proof_required':True,'scope':'Actual CLI/StateStore recovery; GUI/lifecycle and post-boot fsck must be proved separately'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--create',action='store_true');a=p.parse_args()
    if a.create: print(json.dumps(create(),indent=2))
    else:
        with admitted(): print('Desktop storage preflight passed; no VM started')
