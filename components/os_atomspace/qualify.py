"""Actual PeTTa/Omega ingestion/query probe with explicitly synthetic OS claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO));sys.path.insert(0,str(ROOT.parent/'conversation'))
from components.os_atomspace.contract import canonical,digest,validate,PHASES
from learning import finalize_process
from cognition import write_record


def fixture(sequence,phases):
    evidence={'fixture':True,'source':'synthetic test; no package manager executed','sequence':sequence}
    sha=digest(evidence)
    return {'schema':'roko.os-state.claims.v0','backend':'synthetic','machine':'fixture-machine',
        'boot':'fixture-boot','producer':'native-query-test','sequence':sequence,
        'evidence':[{'sha256':sha,'body':evidence}],
        'facts':[{'phase':phase,'subject':'package-example','generation':'old-running' if phase=='running' else 'new-desired',
                  'value':{'state':phase,'label':'Text with quotes " and literal \\n; !(shell arbitrary)'},
                  'evidence_sha256':sha} for phase in phases]}


def verify(profile):
    for path,sha in profile['files'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:
            raise ValueError('Symbolic/source closure changed: '+path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--symbolic-profile',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--os-fact')
    parser.add_argument('--os-receipt')
    parser.add_argument('--os-source-commit')
    parser.add_argument('--built-ledger','--os-ledger',dest='os_ledger')
    parser.add_argument('--os-machine')
    parser.add_argument('--os-backend')
    parser.add_argument('--os-profile-facts')
    parser.add_argument('--os-profile-receipts')
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    profile=json.loads(Path(args.symbolic_profile).read_bytes());verify(profile)
    files=list(ROOT.glob('*.py'))+list(ROOT.glob('*.pl'))+[ROOT.parent/'conversation'/p for p in
        ('fresh_supervise.py','learning.py','cognition.py','assertions.py')]+[REPO/'omega-baseline/scripts/no-network.py']
    profile['files'].update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    write_record(args.output/'profile.json',profile)
    rows=[];started=time.monotonic()
    native_import=any((args.os_fact,args.os_receipt))
    ledger_import=any((args.os_ledger,args.os_machine,args.os_backend))
    profile_import=any((args.os_profile_facts,args.os_profile_receipts))
    if sum((native_import,ledger_import,profile_import))>1:
        raise ValueError('Choose one OS-owner evidence source')
    if profile_import:
        if not all((args.os_profile_facts,args.os_profile_receipts,args.os_source_commit)):
            raise ValueError('All OS-owner profile source options required')
        from components.os_atomspace.owner_profile import import_profile_history
        packets=[import_profile_history(Path(args.os_profile_facts).read_bytes(),Path(args.os_profile_receipts).read_bytes(),args.os_source_commit)]
    elif ledger_import:
        if not all((args.os_ledger,args.os_machine,args.os_backend)):
            raise ValueError('All OS ledger query options required')
        if not Path(args.os_ledger).is_file():
            raise ValueError('Require an existing durable OS-state ledger')
        from components.os_atomspace.ledger import Ledger
        ledger=Ledger(args.os_ledger)
        try:state=ledger.snapshot(args.os_machine,args.os_backend)
        finally:ledger.close()
        if state['packet'] is None:raise ValueError('No durable OS-state snapshot')
        packets=[state['packet']]
    elif native_import:
        if not all((args.os_fact,args.os_receipt,args.os_source_commit)):
            raise ValueError('All OS-owner v1 source options required')
        from components.os_atomspace.os_fact_v1 import import_built_fact
        packets=[import_built_fact(Path(args.os_fact).read_bytes(),Path(args.os_receipt).read_bytes(),args.os_source_commit)]
    else:
        packets=[fixture(0,['desired']),fixture(1,PHASES),fixture(2,[])]
    for index,packet in enumerate(packets):
        packet=validate(packet);directory=args.output/str(index);directory.mkdir(mode=0o700)
        write_record(directory/'input.json',packet);verify(profile)
        stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
        command=[profile['python'],'-B',str(REPO/'omega-baseline/scripts/no-network.py'),
            profile['python'],'-B',str(ROOT.parent/'conversation/fresh_supervise.py'),
            '--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','15','--',
            profile['swipl'],'--stack-limit=64m','-q','-f','none','--no-packs','-s',str(ROOT/'worker.pl'),'--','silent']
        environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
                     **profile.get('runtime_env',{}),'PETTA_PATH':profile['petta'],'OMEGA_PATH':profile['omega']}
        environment['PYTHONPATH']=str(ROOT)+os.pathsep+environment.get('PYTHONPATH','')
        proc=None;out=err=b'';failure=None;response=None
        try:
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=environment,start_new_session=True)
            out,err=proc.communicate(canonical(packet),timeout=22)
            if proc.returncode or len(out)>65536 or len(err)>65536 or b'descendants_cleaned=1' not in err:
                raise ValueError('Native OS-state query execution/finalization failed')
            response=json.loads(out)
            if (response['snapshot_sha256']!=digest(packet) or response['verified_native_os_state'] is not False
                    or response['mutation_authority'] is not False or response['executed_actions']!=0):
                raise ValueError('Native representation/provenance mismatch')
            for phase in PHASES:
                if response['results'][phase]!=[r for r in packet['facts'] if r['phase']==phase]:
                    raise ValueError('Native phase isolation mismatch')
            verify(profile)
        except BaseException as error:failure=error
        out,err,failure,errors,fragments=finalize_process(proc,out,err,failure)
        receipt={'status':'passed' if failure is None else 'failed','stdout_hex':out.hex(),'stderr_hex':err.hex(),
                 'finalization_errors':errors,'output_fragments':fragments,'error':None if failure is None else repr(failure)}
        try:
            write_record(directory/'receipt.json',receipt)
        except BaseException as error:
            errors.append({'stage':'receipt-write','type':type(error).__name__,'error':str(error)})
            failure=failure or error
            receipt.update(status='failed',error=repr(failure))
        if failure is not None:
            failure.receipt=receipt;raise failure
        rows.append(response)
    result={'status':'passed','cases':rows,'seconds':time.monotonic()-started,'actual_runtime':'PeTTa with upstream Omega modules',
            'os_receipts':'external OS-owner observed Nix private-profile history with canonical predecessor hashes' if profile_import else
                'durable external OS-owner v1 built fact with hash-bound Nix receipt' if ledger_import else
                'external OS-owner v1 built fact with hash-bound Nix receipt' if native_import else 'synthetic fixtures only',
            'verified_native_nix_guix':False,'executed_actions':0}
    write_record(args.output/'result.json',result)
    print(json.dumps({'status':result['status'],'cases':len(rows),'seconds':result['seconds'],'verified_native_nix_guix':False}))


if __name__=='__main__':main()
