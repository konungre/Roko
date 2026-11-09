"""Read/hash existing sources only. Does not stage, chmod, build or execute."""
import hashlib,json,stat
from pathlib import Path

HERE=Path(__file__).resolve().parent
W=HERE.parent
G=Path('/run/roko-guest-cognition/symbolic-v1')
I=Path('/opt/roko/desktop/live-request')
old=W/'symbolic-ai-v4/proof/inputs.json'
assert hashlib.sha256(old.read_bytes()).hexdigest()=='541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0'
lock=json.loads(old.read_text()); entries={}; verification=[]
roots={W/'recovery-second/runtime/swipl-basic/runtime/swipl/lib/swipl':'swipl',
 W/'recovery-second/runtime/swipl-basic/runtime/recovered-python312':'python',
 W/'omega-baseline/vendor/PeTTa-omega-release':'petta',
 W/'omega-baseline/vendor/PeTTa/repos/Omega':'omega',
 W/'symbolic-ai-v4/private-ecan':'private-ecan',W/'symbolic-ai-v4/system':'system'}

def measured(p,expected=None):
 p=Path(p); b=p.read_bytes();info=p.stat();sha=hashlib.sha256(b).hexdigest()
 if expected is not None:
  assert sha==expected['sha256'] and len(b)==expected['bytes'],str(p)
 return {'source':str(p),'source_realpath':str(p.resolve()),'source_mode':stat.S_IMODE(info.st_mode),
  'mode':0o555 if info.st_mode&0o111 else 0o444,'bytes':len(b),'sha256':sha,'elf':b[:4]==b'\x7fELF'}

for name,row in lock['files'].items():
 p=Path(name)
 for source,sub in roots.items():
  if p.is_relative_to(source):
   dest=str(G/sub/p.relative_to(source));assert dest not in entries
   entries[dest]=measured(p,row);break
for name,target in lock['symlinks'].items():
 p=Path(name);assert str(p.readlink())==target
 for source,sub in roots.items():
  if p.is_relative_to(source):
   dest=str(G/sub/p.relative_to(source));entries[dest]=measured(p)
   entries[dest]['flattened_alias']=True;break
for p in sorted((HERE/'capsule-bridge').iterdir()):
 if p.is_file():entries[str(G/'bridge'/p.name)]=measured(p)
entries[str(G/'metta-attention-source.lock.json')]=measured(W/'omega-baseline/metta-attention-source.lock.json')
files={name:{k:row[k] for k in ('bytes','mode','sha256','elf')} for name,row in entries.items()}
trees={}
for sub in ('swipl','python','petta','omega','private-ecan','system','bridge'):
 root=G/sub;members=set()
 for name in files:
  p=Path(name)
  if not p.is_relative_to(root):continue
  rel=p.relative_to(root);members.add(str(rel))
  members.update(str(parent) for parent in rel.parents if str(parent)!='.')
 trees[str(root)]=[str(p) for p in sorted(Path(m) for m in members)]
future={'version':1,'files':files,'tree_entries':trees,'symlinks':{},
 'native_tested':False,'status':'prospective guest paths, not installed or admitted'}
raw=(json.dumps(future,indent=2,sort_keys=True)+'\n').encode()
(HERE/'proof/prospective-capsule-inputs.json').write_bytes(raw)
endpoint={}
for p in (HERE/'source').iterdir():
 if p.is_file():endpoint[str(I/p.name)]=measured(p)
for n in ('working_state.py','state_store.py'):
 endpoint[str(I/n)]=measured(W/'omega-baseline/adapters'/n)
bootstrap={str(Path('/usr/lib/roko-unprivileged')/p.name):measured(p) for p in sorted((HERE/'root-bootstrap').iterdir()) if p.is_file()}
plan={'version':1,'source_only':True,'native_executed':False,'model_executed':False,'VM_started':False,
 'materialized':False,'enabled_by_default':False,'guest_controller_abi':'fixed /usr/bin/python3.13 -I -B',
 'private_native_abi':'SWI10.0.2 + Janus + Python3.12.14, separate child process',
 'context_operation_count':{'ecan':1,'omega_literal':1},'model_residency':'context children fully stopped before model startup',
 'capsule_placement':str(G),'capsule_entries':entries,'endpoint_entries':endpoint,'bootstrap_entries':bootstrap,
 'bootstrap_receipt':{'path':'/run/roko-control/native-context-bootstrap.json','cap_bytes':8192,'owner':0,'group':1000,'mode':0o440,'created_only_by_existing_root_PID1':True,'enabled_by_default':False,'authority':'storage observation only'},
 'request_storage':{'path':'/var/lib/roko/live-requests','filesystem':'existing private tmpfs','total_bytes':128*1024**2,'free_floor_bytes':32*1024**2,'native_request_cap':32,'mount_or_directory_permission_changes':False},
 'capsule_file_count':len(entries),'capsule_payload_bytes':sum(x['bytes'] for x in entries.values()),
 'capsule_cap_bytes':128*1024**2,'prospective_manifest_sha256':hashlib.sha256(raw).hexdigest(),
 'inputs_lock_source_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
 'license_restriction':'Private ECAN raw sources are measured but excluded from redistributable archives; no licensed redistribution claim.',
 'remaining_gate':'Source review only. Separately reconcile current non-root session plan; stage one private capsule; bind endpoint/root source anchors and actual capsule manifest; qualify root storage receipt and non-root endpoint in guest before enablement. No execution permission from this map.'}
assert plan['capsule_payload_bytes']+len(raw)<plan['capsule_cap_bytes']
(HERE/'proof/staging-plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in plan.items() if k not in ('capsule_entries','endpoint_entries','bootstrap_entries')},indent=2))
