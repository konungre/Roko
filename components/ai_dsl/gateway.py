"""Hash-qualified, supervised local AI-DSL search with independent proof checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT.parent/'conversation'))
from components.ai_dsl.contract import canonical, validate, check
from components.nars_hyperon.source.runtime import verify
from cognition import write_record
from learning import finalize_process


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(guard_path, evidence_root):
    guard_path = Path(guard_path).resolve(strict=True)
    guard = json.loads(guard_path.read_bytes())
    admission = sha(guard_path)
    verify(guard, admission)
    paths = list(ROOT.glob('*.py')) + [p for p in (ROOT/'upstream').iterdir() if p.is_file()]
    paths += [ROOT/'upstream/LICENSE',ROOT/'upstream/NOTICE',guard_path,
              Path(guard['python']),Path(sys.executable).resolve(),
              REPO/'omega-baseline/scripts/no-network.py']
    paths += [ROOT.parent/'conversation'/name for name in
              ('fresh_supervise.py','learning.py','cognition.py','assertions.py')]
    pins = dict(guard['files'])
    pins.update({str(p):sha(p) for p in paths})
    return {'version':1,'python':str(Path(sys.executable).resolve()),'guard_manifest':str(guard_path),
            'guard_admission':admission,'evidence_root':str(Path(evidence_root).absolute()),'files':pins}


def verify_profile(profile):
    if type(profile) is not dict or set(profile) != {'version','python','guard_manifest','guard_admission','evidence_root','files'} or profile['version'] != 1:
        raise ValueError('AI-DSL profile schema')
    for path,digest in profile['files'].items():
        if not Path(path).is_absolute() or sha(path)!=digest:
            raise ValueError('AI-DSL closure changed')
    for path in (profile['python'],profile['guard_manifest'],str(ROOT/'worker.py'),str(ROOT/'contract.py'),str(ROOT/'gateway.py')):
        if path not in profile['files']:
            raise ValueError('Missing AI-DSL executable/source pin')
    for path in list(ROOT.glob('*.py')) + [p for p in (ROOT/'upstream').iterdir() if p.is_file()]:
        if profile['files'].get(str(path)) != sha(path):
            raise ValueError('Missing AI-DSL source closure')
    if profile['files'][profile['guard_manifest']]!=profile['guard_admission']:
        raise ValueError('Unpinned runtime guard')
    guard=json.loads(Path(profile['guard_manifest']).read_bytes())
    verify(guard,profile['guard_admission'])
    for path,digest in guard['files'].items():
        if profile['files'].get(path)!=digest:
            raise ValueError('Missing Hyperon closure')
    return guard


def run(request, profile):
    request=validate(request)
    guard=verify_profile(profile)
    root=Path(profile['evidence_root'])
    if not root.is_absolute():
        raise ValueError('Require absolute evidence root')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    directory=Path(tempfile.mkdtemp(prefix='ai-dsl-',dir=root))
    write_record(directory/'request.json',request)
    stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
    command=[profile['python'],'-B',str(REPO/'omega-baseline/scripts/no-network.py'),
        profile['python'],'-B',str(ROOT.parent/'conversation/fresh_supervise.py'),
        '--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','12','--',guard['prlimit'],
        '--cpu=5:5','--as=536870912:536870912','--nofile=64:64','--core=0:0','--',
        guard['python'],'-I','-B',str(ROOT/'worker.py'),profile['guard_manifest'],profile['guard_admission']]
    proc=None;out=err=b'';failure=None;result=None
    try:
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            start_new_session=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
        out,err=proc.communicate(canonical(request),timeout=20)
        if proc.returncode or len(out)>65536 or len(err)>65536 or b'descendants_cleaned=1' not in err:
            raise ValueError('AI-DSL native execution/finalization failed')
        packet=json.loads(out)
        if (set(packet)!={'request','proofs','query','definitions_sha256','upstream_commit','network_denied','executed_services','executed_actions'}
                or packet['request']!=request or packet['network_denied'] is not True
                or packet['executed_services']!=0 or packet['executed_actions']!=0):
            raise ValueError('AI-DSL native request/authority mismatch')
        lock=json.loads((ROOT/'upstream/source-lock.json').read_bytes())
        if packet['upstream_commit']!=lock['commit']:
            raise ValueError('AI-DSL source mismatch')
        definitions=(ROOT/'upstream/rse-combinator-xp.metta').read_text().split(';;;;;;;;;;\n;; Test ;;\n;;;;;;;;;;')[0]
        if packet['definitions_sha256']!=hashlib.sha256(definitions.encode()).hexdigest():
            raise ValueError('AI-DSL loaded definition mismatch')
        result=check(request,packet['proofs'])
        verify_profile(profile)
    except BaseException as error:
        failure=error
    out,err,failure,errors,fragments=finalize_process(proc,out,err,failure)
    receipt={'status':'passed' if failure is None else 'failed','request':request,
        'stdout_hex':out.hex(),'stderr_hex':err.hex(),'finalization_errors':errors,'output_fragments':fragments,
        'returncode':None if proc is None else proc.returncode,'error':None if failure is None else repr(failure),
        'executed_services':0,'executed_actions':0,'evidence_directory':str(directory)}
    if failure is None:receipt['response']=result
    try:
        write_record(directory/'receipt.json',receipt)
    except BaseException as error:
        errors.append({'stage':'receipt-write','type':type(error).__name__,'error':str(error)})
        failure=failure or error
        receipt.update(status='failed',error=repr(failure))
    if failure is not None:
        failure.receipt=receipt
        raise failure
    return result,receipt
