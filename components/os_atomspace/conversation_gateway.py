"""Query pinned OS-owner private-profile evidence in actual local PeTTa/Omega."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import stat

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO));sys.path.insert(0,str(ROOT.parent/'conversation'))
from components.os_atomspace.contract import canonical,digest,PHASES
from components.os_atomspace.owner_profile import import_profile_history
from components.os_atomspace.conversation_contract import validate
from cognition import write_record
from learning import finalize_process


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_source(path,limit):
    # Optional data can disappear or become a special file. Never block on a
    # FIFO or follow a replacement symlink while checking availability.
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):raise OSError('Receipt source is not a regular file')
        if before.st_size>limit:raise ValueError('Receipt source byte cap')
        raw=b''
        while len(raw)<=limit:
            chunk=os.read(fd,min(4096,limit+1-len(raw)))
            if not chunk:break
            raw+=chunk
        after=os.fstat(fd)
        if len(raw)>limit:raise ValueError('Receipt source byte cap')
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise OSError('Receipt source changed during read')
        return raw
    finally:os.close(fd)


def parse_source(profile,facts_raw,receipts_raw):
    for key,raw in (('facts_path',facts_raw),('receipts_path',receipts_raw)):
        if hashlib.sha256(raw).hexdigest()!=profile['files'][profile[key]]:
            raise ValueError('OS observation source bytes changed')
    return import_profile_history(facts_raw,receipts_raw,profile['source_commit'])


def source_packet(profile):
    return parse_source(profile,read_source(profile['facts_path'],16384),read_source(profile['receipts_path'],32768))


def verify_runtime(profile, *, include_sources=False):
    if (type(profile) is not dict or set(profile)!={'schema','runtime','facts_path','receipts_path','source_commit','files'}
            or profile['schema']!='roko.os-atomspace.conversation-profile.v1'):
        raise ValueError('OS observation profile schema')
    runtime=profile['runtime']
    if (type(runtime) is not dict or set(runtime)!={'swipl','python','petta','omega','runtime_env'}
            or type(runtime['runtime_env']) is not dict):
        raise ValueError('OS observation runtime schema')
    for name in ('swipl','python','petta','omega'):
        if type(runtime[name]) is not str or not Path(runtime[name]).is_absolute():
            raise ValueError('Absolute OS observation runtime selector required')
    if any(type(key) is not str or type(value) is not str for key,value in runtime['runtime_env'].items()):
        raise ValueError('OS observation runtime environment schema')
    data_paths={profile['facts_path'],profile['receipts_path']}
    for path in data_paths:
        expected=profile['files'].get(path)
        if (not Path(path).is_absolute() or type(expected) is not str or len(expected)!=64
                or any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('Unpinned OS observation data source')
    for path,expected in profile['files'].items():
        if path in data_paths:continue
        if not Path(path).is_absolute() or sha(path)!=expected:
            raise ValueError('OS observation source/runtime changed')
    entrypoints=[Path(runtime['python']),Path(runtime['swipl']),Path(runtime['petta'])/'src/metta.pl']
    entrypoints += [Path(runtime['omega'])/'src'/name for name in ('utils.py','loop.metta','providers.metta','providers.py')]
    for path in entrypoints:
        if str(path) not in profile['files'] or profile['files'][str(path)]!=sha(path):
            raise ValueError('Unpinned OS observation runtime entrypoint')
    paths=list(ROOT.glob('*.py'))+list(ROOT.glob('*.pl'))
    paths += [Path(profile['runtime'][name]) for name in ('swipl','python')]
    paths += [ROOT.parent/'conversation'/name for name in ('fresh_supervise.py','learning.py','cognition.py','assertions.py')]
    paths += [REPO/'omega-baseline/scripts/no-network.py']
    for path in paths:
        if profile['files'].get(str(path))!=sha(path):
            raise ValueError('Missing OS observation closure pin')
    if include_sources:
        for key,limit in (('facts_path',16384),('receipts_path',32768)):
            if hashlib.sha256(read_source(profile[key],limit)).hexdigest()!=profile['files'][profile[key]]:
                raise ValueError('OS observation source bytes changed')


def verify_profile(profile):
    verify_runtime(profile,include_sources=True)
    return source_packet(profile)


def prepare(symbolic_profile,facts_path,receipts_path,source_commit):
    symbolic=json.loads(Path(symbolic_profile).read_bytes())
    for path,expected in symbolic['files'].items():
        if sha(path)!=expected:raise ValueError('Symbolic runtime closure changed')
    runtime={key:symbolic[key] for key in ('swipl','python','petta','omega')}
    runtime['runtime_env']=dict(symbolic.get('runtime_env',{}))
    profile={'schema':'roko.os-atomspace.conversation-profile.v1','runtime':runtime,
        'facts_path':str(Path(facts_path).resolve(strict=True)),
        'receipts_path':str(Path(receipts_path).resolve(strict=True)),
        'source_commit':source_commit,'files':dict(symbolic['files'])}
    paths=list(ROOT.glob('*.py'))+list(ROOT.glob('*.pl'))
    paths += [Path(profile[name]) for name in ('facts_path','receipts_path')]
    paths += [ROOT.parent/'conversation'/name for name in ('fresh_supervise.py','learning.py','cognition.py','assertions.py')]
    paths += [REPO/'omega-baseline/scripts/no-network.py']
    profile['files'].update({str(p):sha(p) for p in paths})
    verify_profile(profile)
    return profile


def run(request,profile,directory):
    request=validate(request);packet=verify_profile(profile);snapshot=digest(packet)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    write_record(directory/'start.json',{'request':request,'packet':packet,'snapshot_sha256':snapshot})
    runtime=profile['runtime']
    stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
    command=[runtime['python'],'-B',str(REPO/'omega-baseline/scripts/no-network.py'),
        runtime['python'],'-B',str(ROOT.parent/'conversation/fresh_supervise.py'),
        '--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','15','--',
        runtime['swipl'],'--stack-limit=64m','-q','-f','none','--no-packs','-s',str(ROOT/'worker.pl'),'--','silent']
    environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
        **runtime.get('runtime_env',{}),'PETTA_PATH':runtime['petta'],'OMEGA_PATH':runtime['omega']}
    environment['PYTHONPATH']=str(ROOT)+os.pathsep+environment.get('PYTHONPATH','')
    proc=None;out=err=b'';failure=None;response=None
    try:
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=environment,start_new_session=True)
        out,err=proc.communicate(canonical(packet),timeout=22)
        if proc.returncode or len(out)>65536 or len(err)>65536 or b'descendants_cleaned=1' not in err:
            raise ValueError('OS observation native execution/finalization failed')
        native=json.loads(out)
        if (native['snapshot_sha256']!=snapshot or native['verified_native_os_state'] is not False
                or native['mutation_authority'] is not False or native['executed_actions']!=0
                or native['network_denied'] is not True):
            raise ValueError('OS observation authority/snapshot mismatch')
        for phase in PHASES:
            if native['results'][phase]!=[row for row in packet['facts'] if row['phase']==phase]:
                raise ValueError('OS observation phase query mismatch')
        if digest(verify_profile(profile))!=snapshot:
            raise ValueError('OS observation changed during query')
        response={'version':1,'operation':request['operation'],'source_commit':profile['source_commit'],
            'source_schema':'roko-os-fact-v1','source_revision':packet['sequence'],
            'machine':packet['machine'],'backend':packet['backend'],'snapshot_sha256':snapshot,
            'latest_observation':native['results']['observed'][0],
            'source_receipts_sha256':profile['files'][profile['receipts_path']],
            'current_host_state_established':False,'system_activation_established':False,
            'running_system_established':False,'health_established':False,
            'producer_authenticated':False,'native_nix_reexecuted_here':False,
            'mutation_authority':False,'executed_actions':0,
            'scope':'imported external Nix private-profile observation queried in local PeTTa/Omega'}
    except BaseException as error:failure=error
    out,err,failure,errors,fragments=finalize_process(proc,out,err,failure)
    receipt={'status':'passed' if failure is None else 'failed','request':request,'snapshot_sha256':snapshot,
        'stdout_hex':out.hex(),'stderr_hex':err.hex(),'finalization_errors':errors,'output_fragments':fragments,
        'returncode':None if proc is None else proc.returncode,'error':None if failure is None else repr(failure),
        'executed_actions':0,'evidence_directory':str(directory)}
    if failure is None:receipt['response']=response
    try:write_record(directory/'receipt.json',receipt)
    except BaseException as error:
        errors.append({'stage':'receipt-write','type':type(error).__name__,'error':str(error)})
        failure=failure or error;receipt.update(status='failed',error=repr(failure))
    if failure is not None:
        failure.receipt=receipt;raise failure
    return response,receipt
