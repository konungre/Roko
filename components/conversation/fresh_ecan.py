"""Actual pinned ECAN attention-bank subset on the fresh PeTTa runtime.

Source is separately acquired, never redistributed in this component. Only
generated symbols and validated integers enter the native program. Text stays
outside ECAN. This ephemeral advisory bank does not authorize actions.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ADAPTER = Path(__file__).resolve().parents[2] / 'omega-baseline/adapters'
sys.path.insert(0, str(ADAPTER))
from native_ecan import COMMIT, MODULES, NativeECANError, _parse, _program, _validate


def verify_source(profile):
    config = profile['ecan']
    root = Path(config['source']).resolve(strict=True)
    lock_path = Path(config['lock']).resolve(strict=True)
    if profile['files'].get(str(lock_path)) != hashlib.sha256(lock_path.read_bytes()).hexdigest():
        raise NativeECANError('Unpinned or modified ECAN source lock')
    lock = json.loads(lock_path.read_text())
    if lock.get('commit') != COMMIT:
        raise NativeECANError('Unexpected ECAN source commit')
    for name, digest in lock['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise NativeECANError('Unsafe ECAN source path')
        path = root / relative
        if profile['files'].get(str(path)) != digest or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise NativeECANError('ECAN source mismatch: '+name)
    return root, lock


def rank_candidates(candidates, *, focus_size=4, profile):
    candidates = _validate(candidates, focus_size, 30)
    source, lock = verify_source(profile)
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='native-bank-', dir=profile['ecan']['scratch']) as directory:
        work = Path(directory)
        copied = work/'metta-attention'
        copied.mkdir()
        for module in MODULES:
            relative = module+'.metta'
            destination = copied/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((source/relative).read_bytes())
        program = copied/'advisory.metta'
        program.write_text(_program(candidates, focus_size))
        parent_start = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
        environment = {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
                       'HOME':directory,'TMPDIR':directory,'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}
        environment.update(profile['runtime_env'])
        command = [profile['python'],'-B',str(here/'fresh_supervise.py'),
                   '--parent-pid',str(os.getpid()),'--parent-start',parent_start,'--seconds','30','--',
                   profile['python'],'-B',str(here.parents[1]/'omega-baseline/scripts/no-network.py'),
                   profile['swipl'],'--stack-limit=64m','-q','-f','none','--no-packs',
                   '-s',str(Path(profile['petta'])/'src/main.pl'),'--',str(program)]
        started = time.monotonic()
        process = subprocess.Popen(command,cwd=work,env=environment,stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            out,err=process.communicate(timeout=40)
        except BaseException:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            raise
        receipt={'implementation':'native-metta-ecan-attention-bank-subset','commit':COMMIT,
                 'seconds':round(time.monotonic()-started,3),'returncode':process.returncode,
                 'stdout':out,'stderr':err,'network_denied':True,
                 'source_files_verified':len(lock['files']),'executed_actions':0}
        if process.returncode or 'ERROR:' in out+err or '❌' in out+err or 'descendants_cleaned=1' not in err:
            raise NativeECANError('Native ECAN failed: '+json.dumps(receipt))
        result = _parse(out,candidates,focus_size)
        verify_source(profile)
        receipt['source_prepost_verified']=True
        receipt['source_lock_sha256']=profile['files'][str(Path(profile['ecan']['lock']).resolve())]
        return result,receipt
