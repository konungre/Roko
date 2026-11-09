"""Admit exact new controls stage into a tiny test seed; never assemble on import."""
import hashlib,importlib.util,json,stat
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1]
s=importlib.util.spec_from_file_location('controls_base_delta',R/'boot/test-delta-root/prepare.py');base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
ROOT_ID=base.ROOT_ID;ROOT_SHA=base.ROOT_SHA;derive_init=base.derive_init
STAGE=R.parent/'roko-corner-stage-v2';LOCK=R.parent/'roko-corner-stage-v2.lock.json';OBSERVER=R.parent/'roko-corner-observe-v2.py'
LOCK_SHA='6560fb28b79d6a9186de0be13352da2bbbd35bffb41cf49bf77f8081c8ef74b4'
OBSERVER_SHA='982856e8cbf22c4557d5505fa48dfe4e0948e29fc3032c1eb454b131512d9935'
def sha(x):return hashlib.sha256(x).hexdigest()
def prepare(which='corner'):
 if which!='corner':raise ValueError('Controls-only stage')
 raw,_=base.read_regular(LOCK.parent,LOCK.name,digest=LOCK_SHA);locked=json.loads(raw)
 actual={str(p.relative_to(STAGE)) for p in STAGE.rglob('*') if not p.is_dir()}
 if actual!=set(locked):raise ValueError('Stage entry set differs')
 values={};records=[]
 def add(path,data,mode,source):
  base.safe_name(path)
  if path in values:raise ValueError('Duplicate output')
  values[path]=(data,mode);records.append(dict(path=path,sha256=sha(data),mode=mode,bytes=len(data),source=source))
 for path,digest in sorted(locked.items()):
  data,mode=base.read_regular(STAGE,path,digest=digest);add('corner/'+path,data,mode,str(STAGE/path))
 data,mode=base.read_regular(OBSERVER.parent,OBSERVER.name,digest=OBSERVER_SHA);add('corner/observe.py',data,mode,str(OBSERVER))
 env=b'# Explicit isolated GUI test; no model/controller override or autostart.\nrc() { /usr/bin/python3.13 /run/roko-test-overlay/corner/observe.py /run/roko-test-overlay/corner/usr/share/roko/corner --overlay --perch-active --roko-root /opt/roko --state-dir /root/.local/state/roko-companion-controls >/dev/console 2>&1; }\n'
 add('env.sh',env,0o444,'generated:explicit-test-function');records.sort(key=lambda r:r['path'])
 total=sum(len(x[0]) for x in values.values())
 if total>base.LIMIT:raise ValueError('Delta size limit')
 identity=dict(root_build_id=ROOT_ID,root_sha256=ROOT_SHA,selection='corner-controls-v2',stage_lock_sha256=LOCK_SHA,observer_sha256=OBSERVER_SHA,source_sha256=sha(Path(__file__).read_bytes()),records=records)
 did=sha(json.dumps(identity,sort_keys=True).encode());entries={}
 for path,(data,mode) in values.items():
  name='roko-test-seed/'+path;entries[name]=(data,stat.S_IFREG|mode,0,0)
  for p in Path(name).parents:
   if str(p)!='.':entries.setdefault(str(p),(b'',stat.S_IFDIR|0o700,0,0))
 entries['roko-test-sha256']=((''.join(r['sha256']+'  '+r['path']+'\n' for r in records)).encode(),stat.S_IFREG|0o444,0,0)
 entries['roko-test-install.sh']=(base.installer(records,did),stat.S_IFREG|0o700,0,0)
 return entries,dict(identity,delta_id=did,payload_bytes=total,assembly_performed=False)
if __name__=='__main__':
 _,r=prepare();print(json.dumps(r,indent=2))
