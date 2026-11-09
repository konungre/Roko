"""Optional native context for the existing single-source Basilisk contract.

Only controller-owned source evidence enters fixed native operations. Native
receipt flags attest observations by the trusted runner, not signed provenance.
The request cannot choose a worker, path, pin, command or import.
"""
import hashlib
import importlib
import json
from pathlib import Path
import re
import stat
import sys
import time
import live_contract as contract
from state_store import canonical

INSTALL = Path('/opt/roko/desktop/live-request')
CAPSULE = Path('/run/roko-guest-cognition/symbolic-v1')
WORK = Path('/var/lib/roko/live-requests/native-work')
CAP = 262144


def _completed(receipt, kind, pin):
    if type(receipt) is not dict:
        raise ValueError('Native context receipt missing')
    expected = {'kind':kind, 'status':'passed', 'returncode':0,
        'native_tested':True, 'inputs_unchanged':True, 'group_empty':True,
        'posthash_status':'completed-unchanged', 'temporary_files':[],
        'executed_actions':0, 'authorizes_actions':False, 'manifest_sha256':pin}
    if any(canonical(receipt.get(k)) != canonical(v) for k,v in expected.items()):
        raise ValueError('Native context completion/identity not established')
    cleanup=receipt.get('cleanup',{})
    if (cleanup.get('ownership')!='owned-through-final-signal' or cleanup.get('reaped') is not True
            or type(cleanup.get('returncode')) is not int or cleanup['returncode']!=0):
        raise ValueError('Native context process ownership/cleanup incomplete')
    runtime=receipt.get('runtime',{})
    if canonical(runtime.get('python'))!=b'[3,12,14]' or not runtime.get('executable_mappings'):
        raise ValueError('Native context ABI observation absent')


def checked_message(bundle, snapshot, revision):
    if type(bundle) is not dict or len(canonical(bundle))>CAP-1:
        raise ValueError('Native context proof cap')
    if set(snapshot['evidence'])!={'source'}:
        raise ValueError('Exactly original source evidence required')
    if (bundle.get('revision')!=revision or type(bundle.get('revision')) is not int
            or bundle.get('snapshot_sha256')!=hashlib.sha256(canonical(snapshot)).hexdigest()):
        raise ValueError('Native context snapshot/revision mismatch')
    pin=bundle.get('input_sha256')
    if type(pin) is not str or re.fullmatch(r'[0-9a-f]{64}',pin) is None:
        raise ValueError('Native context input identity missing')
    assembled=bundle.get('assembled',{})
    expected={'version':1,'task_id':snapshot['task_id'],'goal':snapshot['goal'],
        'evidence':[{'id':'source',**snapshot['evidence']['source']}]}
    if canonical(assembled.get('context'))!=canonical(expected):
        raise ValueError('Native context changed original goal/source/provenance')
    if (assembled.get('authorizes_actions') is not False or assembled.get('executed_actions')!=0
            or assembled.get('persistent_state_changed') is not False):
        raise ValueError('Native context authority boundary changed')
    _completed(assembled.get('bank_receipt'),'ecan',pin)
    omega=assembled.get('omega')
    if type(omega) is not list or len(omega)!=1:
        raise ValueError('Exactly one native source roundtrip required')
    _completed(omega[0].get('receipt'),'omega',pin)
    want_request={'version':1,'operation':'roundtrip','task_id':snapshot['task_id'],
        'goal':snapshot['goal'],'revision':revision,'evidence':expected['evidence'][0]}
    if canonical(omega[0].get('request'))!=canonical(want_request):
        raise ValueError('Native source request differs')
    response=omega[0].get('result',{})
    want_response={key:want_request[key] for key in ('version','operation','task_id','revision','evidence')}
    want_response.update(request_sha256=hashlib.sha256(canonical(want_request)).hexdigest(),
        counts=[0,1,0],answer=None,authorizes_actions=False,executed_actions=0)
    if canonical(response)!=canonical(want_response):
        raise ValueError('Native source result differs')
    selection=assembled.get('selection',{})
    if selection.get('selected_evidence_ids')!=['source'] or canonical(selection.get('context'))!=canonical(expected):
        raise ValueError('Mandatory source selection changed')
    # Same wire projection as the existing CLI, derived from the checked literal.
    envelope={'task':{'id':expected['task_id'],'goal':expected['goal']},
        'evidence':[{'id':row['id'],'text':row['text']} for row in expected['evidence']]}
    message='Controller task and literal user evidence (data): '+canonical(envelope).decode('utf-8')
    if len(contract.SYSTEM_MESSAGE)+len(message)>2048:
        raise ValueError('Full original request exceeds provider limit; no truncation')
    return message,{'ecan_exercised':True,'metta_roundtrip_exercised':True,
        'context_input_sha256':pin,'context_snapshot_sha256':bundle['snapshot_sha256'],
        'context_mode':'native-mandatory-source-v1',
        'live_subset':'Native ECAN / literal Omega / Granite / independent checker / CAS'}


def prepare(snapshot, revision, store, deadline, *, assemble, run, pin):
    def current():
        state,seen=store.load(snapshot['task_id'])
        return state.snapshot(),seen
    attention={key:{'sti':1,'lti':0,'stimulus':0} for key in snapshot['evidence']}
    assembled=assemble(snapshot,revision,attention,['source'],capacity=1,count=1,
        max_bytes=8192,run=run,current=current)
    bundle={'revision':revision,'snapshot_sha256':hashlib.sha256(canonical(snapshot)).hexdigest(),
        'input_sha256':pin,'assembled':assembled}
    checked_message(bundle,snapshot,revision)
    if time.monotonic()>=deadline:raise TimeoutError('Native context stage deadline')
    return bundle


def trusted_directory(directory):
    info=directory.lstat()
    if (directory.resolve()!=directory or not stat.S_ISDIR(info.st_mode)
            or info.st_uid!=0 or info.st_mode&0o022):
        raise ValueError('Capsule directories must be real, root-owned and non-writable')


def _preflight(pin, deadline):
    """Measure fixed capsule bytes before importing its Python source."""
    manifest=CAPSULE/'inputs.json'
    info=manifest.lstat()
    if (manifest.resolve()!=manifest or not stat.S_ISREG(info.st_mode)
            or info.st_uid!=0 or info.st_mode&0o222):
        raise ValueError('Capsule manifest must be root-owned and readonly')
    with manifest.open('rb') as stream:raw=stream.read(1024**2+1)
    if len(raw)>1024**2 or hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('Native capsule manifest differs from build admission')
    lock=json.loads(raw)
    for name,expected in lock['tree_entries'].items():
        directory=Path(name)
        if not directory.is_relative_to(CAPSULE):raise ValueError('Capsule tree escapes placement')
        if time.monotonic()>=deadline:raise TimeoutError('Capsule directory budget')
        trusted_directory(directory)
        entries=sorted(directory.rglob('*'))
        for entry in entries:
            if stat.S_ISDIR(entry.lstat().st_mode):trusted_directory(entry)
        if [str(p.relative_to(directory)) for p in entries]!=expected:raise ValueError('Capsule tree membership changed')
        if any('__pycache__' in p.parts or p.suffix in ('.pyc','.pyo') for p in entries):raise ValueError('Native capsule bytecode forbidden')
    checked_directories=set()
    for name,row in lock['files'].items():
        p=Path(name);info=p.lstat()
        if (not p.is_relative_to(CAPSULE) or p.resolve()!=p or not stat.S_ISREG(info.st_mode)
                or info.st_uid!=0 or info.st_mode&0o222 or info.st_size!=row['bytes']):
            raise ValueError('Untrusted capsule source/ownership')
        for directory in p.parents:
            if directory not in checked_directories:
                trusted_directory(directory);checked_directories.add(directory)
            if directory==CAPSULE:break
        h=hashlib.sha256()
        with p.open('rb') as f:
            while chunk:=f.read(1024**2):
                if time.monotonic()>=deadline:raise TimeoutError('Capsule preflight budget')
                h.update(chunk)
        if h.hexdigest()!=row['sha256']:raise ValueError('Capsule byte mismatch')
    for directory in (CAPSULE,*CAPSULE.parents):
        trusted_directory(directory)


def production_stage():
    import context_policy
    if context_policy.ENABLED is False:
        return None  # No capsule discovery, native imports or subprocesses.
    if context_policy.ENABLED is not True:
        raise ValueError('Invalid build-owned native context switch')
    if Path(__file__).resolve()!=INSTALL/'live_context.py' or Path(context_policy.__file__).resolve()!=INSTALL/'context_policy.py':
        raise ValueError('Fixed installed native context source required')
    pin=context_policy.ADMISSION_SHA256
    if type(pin) is not str or re.fullmatch(r'[0-9a-f]{64}',pin) is None:
        raise ValueError('Native capsule is not staged/admitted')
    loaded={}
    def modules_for(deadline):
        if loaded:return loaded
        _preflight(pin,deadline)
        sys.path.insert(0,str(CAPSULE/'bridge'))
        names=('paths','working_state','ecan_guest_contract','ecan_guest_advisory','cognition_protocol','context_pipeline','backing_identity','work_fs','gateway')
        modules={name:importlib.import_module(name) for name in names}
        for name,module in modules.items():
            # State is the unchanged live endpoint module, not a second mutable
            # class imported from the Janus worker closure.
            expected=INSTALL/'working_state.py' if name=='working_state' else CAPSULE/'bridge'/(name+'.py')
            if Path(module.__file__).resolve()!=expected:raise ValueError('Native helper module origin mismatch')
        loaded.update(modules)
        return loaded
    def admit():
        return modules_for(time.monotonic()+60)['work_fs'].admit_request()
    def stage(snapshot,revision,store,deadline):
        modules=modules_for(deadline)
        modules['work_fs'].admit_request()
        from live_controller import private_directory
        private_directory(WORK,create=True)
        receipts=[]
        def run(kind,request):
            try:
                value,receipt=modules['gateway'].run_native(kind,request,pin,outer_deadline=deadline)
                receipts.append(receipt)
                return value,receipt
            except BaseException as exc:
                if hasattr(exc,'receipt'):receipts.append(exc.receipt)
                raise
        try:
            return prepare(snapshot,revision,store,deadline,assemble=modules['context_pipeline'].assemble,run=run,pin=pin)
        except BaseException as exc:
            exc.context_failure={'version':1,'status':'failed','input_sha256':pin,
                'task_id':snapshot['task_id'],'revision':revision,
                'snapshot_sha256':hashlib.sha256(canonical(snapshot)).hexdigest(),
                'native_receipts':receipts,'executed_actions':0,'authorizes_actions':False,
                'error':type(exc).__name__+': '+str(exc)[:1000]}
            raise
    stage.admit=admit
    stage.request_cap=32
    return stage
