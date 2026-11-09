"""Separate combined graphical model candidate. No host services or model copies."""
import difflib,gzip,hashlib,importlib.util,json,stat,sys
from pathlib import Path
H=Path(__file__).resolve().parent; R=H.parents[1]
sys.path.insert(0,str(R/'boot/granite-model-guest-fourcore'))
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
guest=load('combined_fourcore',R/'boot/granite-model-guest-fourcore/run_fourcore.py')
corner=load('combined_corner',R/'boot/companion-controls-guest/delta.py')
archive=guest.base.archive
OUT=R/'build-src/companion-model-guest/stage-v1'
def sha(x):return hashlib.sha256(x).hexdigest()
def replace(data,old,new):
 if data.count(old)!=1:raise ValueError('Exact transformation anchor changed: '+repr(old))
 return data.replace(old,new)
def cli_variant(data):
 old=b" if not model_lock.is_file() or not (ROOT/json.loads(model_lock.read_text())['path']).is_file() or not (ROOT/'vendor/PeTTa/repos/Omega/src/providers.py').is_file():\n"
 new=b''' raw_lock=ROOT/'granite-raw-transport.lock.json'
 runtime_lock=ROOT/'granite-portable-runtime.lock.json'
 raw_mode=False
 if raw_lock.is_file():
  raw=json.loads(raw_lock.read_text());runtime=json.loads(runtime_lock.read_text())
  if raw.get('status')!='raw-model-transport-admitted' or raw.get('reviewed_admission') is not True or runtime.get('status')!='candidate-runtime-admitted-for-single-probe' or runtime.get('files',{}).get('granite-raw-transport.lock.json')!=__import__('hashlib').sha256(raw_lock.read_bytes()).hexdigest():
   raise ValueError('Raw guest provider manifest is not explicitly admitted')
  raw_mode=True
 if not model_lock.is_file() or (not raw_mode and not (ROOT/json.loads(model_lock.read_text())['path']).is_file()) or not (ROOT/'vendor/PeTTa/repos/Omega/src/providers.py').is_file():
'''
 data=replace(data,old,new)
 # Diagnostic data accompanies genuine output; it never alters proposal/check logic.
 data=replace(data,b"'seconds':provider.last.get('elapsed_seconds'),'executed_actions':0}",b"'seconds':provider.last.get('elapsed_seconds'),'executed_actions':0,'guest_diagnostics':{'backend':provider.backend,'raw_model_checks':provider._raw_model.report,'native':provider.last}}")
 return data

def sources(admitted=False):
 entries,plan=guest.base.prepared_delta(execution_admitted=admitted)
 files={name.removeprefix('granite-model-probe/'):(v[0],stat.S_IMODE(v[1])) for name,v in entries.items() if name.startswith('granite-model-probe/roko/') and stat.S_ISREG(v[1])}
 diffs={}
 def changed(name,old,new):
  diffs[name]=''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='preserved/'+name,tofile='combined/'+name))
  return new
 n='roko/adapters/granite_guest.py';old=files[n][0]
 new=replace(old,b'import providers\n',b'import providers\nimport sys\n')
 new=replace(new,b"'existing output observed; not exact operation duration'}), flush=True)",b"'existing output observed; not exact operation duration'}), file=sys.stderr, flush=True)")
 files[n]=(changed(n,old,new),files[n][1])
 cli='roko/scripts/roko.py';files[cli]=(changed(cli,files[cli][0],cli_variant(files[cli][0])),files[cli][1])
 runtime=json.loads(files['roko/granite-portable-runtime.lock.json'][0]);runtime['files']['scripts/roko.py']=sha(files[cli][0]);runtime['files']['adapters/granite_guest.py']=sha(files['roko/adapters/granite_guest.py'][0]);files['roko/granite-portable-runtime.lock.json']=((json.dumps(runtime,indent=2)+'\n').encode(),0o444)
 c,cp=corner.prepare()
 for name,v in c.items():
  if name.startswith('roko-test-seed/corner/') and stat.S_ISREG(v[1]):files[name.removeprefix('roko-test-seed/')]=(v[0],stat.S_IMODE(v[1]))
 n='corner/usr/share/roko/corner/task_bridge.py';old=files[n][0]
 new=replace(old,b'not 0 < command_timeout <= 120:',b'not 0 < command_timeout <= 1080:')
 new=replace(new,b'at most 120 seconds',b'at most 1080 seconds')
 # Reject bool explicitly rather than inheriting int's surprising subtype behavior.
 new=replace(new,b"if not isinstance(command_timeout, (int, float))",b"if isinstance(command_timeout, bool) or not isinstance(command_timeout, (int, float))")
 files[n]=(changed(n,old,new),files[n][1])
 n='corner/usr/share/roko/corner/companion.py';old=files[n][0]
 new=replace(old,b"    args=p.parse_args(argv)\n",b"    p.add_argument('--controller-timeout',type=float,default=120,help='Finite local controller command timeout, at most 1080 seconds')\n    args=p.parse_args(argv)\n    if not __import__('math').isfinite(args.controller_timeout) or not 0 < args.controller_timeout <= 1080:p.error('--controller-timeout must be finite, positive and at most 1080')\n")
 new=replace(new,b'python_executable=args.controller_python,progress_callback=',b'python_executable=args.controller_python,command_timeout=args.controller_timeout,progress_callback=')
 files[n]=(changed(n,old,new),files[n][1])
 old=files['corner/observe.py'][0]
 new=replace(old,b'import companion\n',b'''import companion
import task_bridge
original_bridge_run = task_bridge._run
def observed_bridge_run(argv, timeout, cancel_event):
    began=time.monotonic()
    try:
        result=original_bridge_run(argv, timeout, cancel_event)
    except BaseException as error:
        print('ROKO_COMBINED_CLI_EXCEPTION '+json.dumps({'argv':argv,'error':str(error),'seconds':time.monotonic()-began}),flush=True)
        raise
    print('ROKO_COMBINED_CLI_RESULT '+json.dumps({'argv':argv,'timeout':timeout,'seconds':time.monotonic()-began,'returncode':result[0],'stdout':result[1],'stderr':result[2]}),flush=True)
    return result
task_bridge._run=observed_bridge_run
''')
 files['corner/observe.py']=(changed('corner/observe.py',old,new),0o644)
 files['inspect.py']=((H/'inspect_guest.py').read_bytes(),0o444)
 files['env.sh']=(b'''# Explicit combined guest test, no autostart and no host inference.
rc() { /usr/bin/python3.13 /run/roko-test-overlay/corner/observe.py /run/roko-test-overlay/corner/usr/share/roko/corner --overlay --roko-root /run/granite-model-probe/roko --state-dir /root/.local/state/roko-combined --controller-python /usr/bin/python3.13 --controller-timeout 1080 >/dev/console 2>&1; }
ci() { /usr/bin/python3.13 /run/roko-test-overlay/inspect.py >/dev/console 2>&1; }
''',0o444)
 # Extract only the init source, then verify against immutable root-source identity.
 old_archive=load('combined_old_archive',R/'boot/basilisk-avatar-guest/build.py')
 transform=load('combined_root_transform',R/'boot/disk-root-guest/transform.py')
 for name,data,mode,major,minor in old_archive.read_archive(R/'build/cosmic-files-portals-guest/files-portals.cpio.gz'):
  if name=='init':session=transform.session_init(data);break
 else:raise ValueError('Missing original session init')
 expected=json.loads((R/'build/disk-root-guest/root-source.json').read_text())['entries']['usr/libexec/roko-session-init']['sha256']
 if sha(session)!=expected:raise ValueError('Original session init changed')
 new=replace(session,b'$BB sleep 390\n',b'$BB sleep 1410\n')
 files['session-init']=(changed('session-init',session,new),0o755)
 plan.update(graphical=True,bridge_default_seconds=120,bridge_selected_seconds=1080,bridge_absolute_cap_seconds=1080,guest_watchdog_seconds=1410,vm_seconds=1500,source_changes=list(diffs),corner_parent=cp)
 plan['payload_bytes']=sum(len(data) for data,mode in files.values())
 if plan['payload_bytes']>20*1024**2:raise ValueError('Combined payload exceeds20MiB')
 return files,plan,diffs

def freeze():
 files,plan,diffs=sources(admitted=True)
 OUT.mkdir(parents=True,mode=0o700,exist_ok=False)
 for name,(data,mode) in files.items():
  path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(mode)
 lock={'plan':plan,'files':{n:{'sha256':sha(d),'bytes':len(d),'mode':m} for n,(d,m) in files.items()},'source_sha256':{p.name:sha(p.read_bytes()) for p in H.glob('*.py')}}
 (OUT/'manifest.json').write_text(json.dumps(lock,indent=2)+'\n')
 for name,diff in diffs.items():(OUT/(name.replace('/','_')+'.diff')).write_text(diff)
 return lock

def assemble(out):
 lock=json.loads((OUT/'manifest.json').read_text());files={}
 actual_sources={p.name:sha(p.read_bytes()) for p in H.glob('*.py')}
 if actual_sources!=lock['source_sha256']:raise ValueError('Frozen combined source recipe changed')
 for name,pin in lock['files'].items():
  p=OUT/name;data=p.read_bytes()
  if sha(data)!=pin['sha256'] or p.stat().st_size!=pin['bytes'] or stat.S_IMODE(p.stat().st_mode)!=pin['mode'] or p.is_symlink():raise ValueError('Frozen combined input changed: '+name)
  files[name]=(data,pin['mode'])
 base=R/'build/disk-root-guest/bootstrap.cpio.gz';raw=gzip.decompress(base.read_bytes());manifest=json.loads((base.parent/'bootstrap.json').read_text())
 if sha(base.read_bytes())!=manifest['initramfs_sha256'] or archive.inspect(raw)!=manifest['entries']:raise ValueError('Accepted bootstrap changed')
 entries=guest.base.unpack(raw)
 original=entries['init'][0]
 install=b'''$BB mkdir -m 700 /newroot/run/granite-model-probe /newroot/run/roko-test-overlay || fail combined-dirs
$BB cp -a /combined-seed/roko /newroot/run/granite-model-probe/ || fail combined-model-runtime
for item in corner env.sh inspect.py session-init; do $BB cp -a "/combined-seed/$item" /newroot/run/roko-test-overlay/ || fail combined-ui; done
(cd /newroot/run && $BB sha256sum -c /combined.sha256) || fail combined-hashes
echo ROKO_COMBINED_PAYLOAD_READY
'''
 init=replace(original,corner.base.HOOK,install+corner.base.HOOK)
 init=replace(init,b'exec /bin/busybox switch_root /newroot /usr/libexec/roko-session-init\n',b'exec /bin/busybox switch_root /newroot /run/roko-test-overlay/session-init\n')
 entries['init']=(init,stat.S_IFREG|0o755,0,0)
 sums=[]
 for name,(data,mode) in files.items():
  dest='combined-seed/'+name;entries[dest]=(data,stat.S_IFREG|mode,0,0)
  runtime='granite-model-probe/'+name if name.startswith('roko/') else 'roko-test-overlay/'+name
  sums.append(sha(data)+'  '+runtime+'\n')
  for parent in Path(dest).parents:
   if str(parent)!='.':entries.setdefault(str(parent),(b'',stat.S_IFDIR|0o700,0,0))
 entries['combined.sha256']=(''.join(sums).encode(),stat.S_IFREG|0o444,0,0)
 stream=b''.join(archive.entry(n,v,m,i+1,ma,mi) for i,(n,(v,m,ma,mi)) in enumerate(sorted(entries.items())))
 stream+=archive.entry('TRAILER!!!',b'',0,len(entries)+1);stream+=b'\0'*(-len(stream)%512);zipped=gzip.compress(stream,compresslevel=1,mtime=0)
 out.mkdir(mode=0o700,parents=True,exist_ok=False);p=out/'bootstrap.cpio.gz';p.write_bytes(zipped);p.chmod(0o444)
 receipt={'initramfs_sha256':sha(zipped),'initramfs_bytes':len(zipped),'stage_manifest_sha256':sha((OUT/'manifest.json').read_bytes()),'entries':archive.inspect(stream),'plan':lock['plan']}
 (out/'assembly.json').write_text(json.dumps(receipt,indent=2)+'\n');return p,receipt
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');a=p.parse_args()
 print(json.dumps(freeze() if a.freeze else sources()[1],indent=2))
