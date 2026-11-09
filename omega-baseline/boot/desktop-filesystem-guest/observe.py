"""Read-only observer of genuine controller state. Never creates/proposes/checks a task."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

CLI=Path('/opt/roko/scripts/roko.py')
STATE=Path('/var/lib/roko')
TASK='desktop-persist'
GOAL='Desktop recovery'

def snapshot():
    sys.path.insert(0,str(CLI.parents[1]/'adapters'))
    from state_store import StateStore
    store=StateStore(STATE)
    state,revision=store.load(TASK)
    value=state.snapshot()
    if revision!=5 or value['goal']!=GOAL or value['phase']!='closed' or value['executed_actions']!=0:
        raise ValueError('Desktop task is not yet the exact completed fixture')
    if value['evidence']['source']['text']!='Arithmetic: 7 * 8.' or value['proposal']['arguments']!={'text':'56'}:
        raise ValueError('Unexpected evidence/proposal')
    if value['verification']['accepted'] is not True or value['verification']['authorizes_actions'] is not False:
        raise ValueError('Incorrect verification result')
    result=subprocess.run([sys.executable,str(CLI),'--state-dir',str(STATE),'show',TASK],capture_output=True,text=True,timeout=20)
    if result.returncode or json.loads(result.stdout)!={'revision':revision,'state':value}:
        raise ValueError('Fresh actual CLI show differs from StateStore')
    paths=list(STATE.glob('*.json'))
    if paths!=[store.path(TASK)]: raise ValueError('Unexpected persistent tasks')
    for path in [STATE,store.path(TASK),Path(str(store.path(TASK))+'.lock')]:
        info=path.lstat(); directory=path==STATE
        if stat.S_IMODE(info.st_mode)!=(0o700 if directory else 0o600) or info.st_uid!=os.getuid() or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink==1):
            raise ValueError('Unexpected persistent state metadata')
    return {'task':TASK,'revision':revision,'state':value,'checkpoint_sha256':hashlib.sha256(store.path(TASK).read_bytes()).hexdigest()}

def console_processes():
    result=[]
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try: args=path.read_bytes().rstrip(b'\0').decode().split('\0')
        except (OSError,UnicodeError): continue
        if str(CLI) in args and '--state-dir' in args and str(STATE) in args and args[-1:] == ['console']:
            result.append({'pid':int(path.parent.name),'argv':args})
    return result

def phase():
    args=Path('/proc/cmdline').read_text().split()
    values=[x.split('=',1)[1] for x in args if x.startswith('roko.desktop-storage=')]
    if len(values)!=1 or values[0] not in ('write','read'): raise ValueError('Invalid storage phase')
    return values[0]

def main():
    selected=phase(); end=time.monotonic()+350
    while time.monotonic()<end:
        try: value=snapshot()
        except (ValueError,KeyError,OSError,subprocess.SubprocessError):
            time.sleep(.5); continue
        print('ROKO_DESKTOP_STORAGE_STATE '+json.dumps(value,sort_keys=True),flush=True)
        print('ROKO_DESKTOP_STORAGE_CONSOLES '+json.dumps(console_processes(),sort_keys=True),flush=True)
        print('ROKO_DESKTOP_STORAGE_'+selected.upper()+'_PASSED',flush=True)
        return 0
    print('ROKO_DESKTOP_STORAGE_FAILED observer-timeout',flush=True)
    return 1

if __name__=='__main__': raise SystemExit(main())
