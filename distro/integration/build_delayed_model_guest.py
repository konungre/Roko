"""Extend a verified service-manager stage; no model copies, downloads or host mounts."""
import argparse,gzip,hashlib,json,lzma,pathlib,shutil,stat,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent));from build_probe import baseline,FLAGS
p=argparse.ArgumentParser();p.add_argument('base_guest');p.add_argument('model_guest');p.add_argument('kernelroot');p.add_argument('output');a=p.parse_args()
base,model,kernelroot,output=[pathlib.Path(x).resolve() for x in (a.base_guest,a.model_guest,a.kernelroot,a.output)]
manifest=json.loads((base/'manifest.json').read_text())
for name,digest in manifest['files'].items():
 if hashlib.sha256((base/'root'/name).read_bytes()).hexdigest()!=digest:raise ValueError('base stage changed')
output.mkdir(mode=0o700);stage=output/'root';shutil.copytree(base/'root',stage)
model_manifest=json.loads((model/'manifest.json').read_text());model_bytes=(model/'model-files/model.gguf').stat().st_size
(stage/'opt/roko/models').mkdir();shutil.copy2(HERE/'model_asset_probe.py',stage/'opt/roko/model_asset_probe.py')
unit='''[Unit]
Description=Read-only delayed local model asset probe (not inference health)
After=roko-startup-report.service
ConditionPathExists=/opt/roko/models/model.gguf
[Service]
Type=oneshot
RemainAfterExit=true
ExecStart=/opt/python/bin/python3 /opt/roko/model_asset_probe.py --model /opt/roko/models/model.gguf --expected-bytes=MODEL_BYTES --output /run/roko-model-asset/status.json
Environment=PYTHONHOME=/opt/python
Environment=LD_LIBRARY_PATH=/opt/python/lib
Environment=PYTHONDONTWRITEBYTECODE=1
DynamicUser=true
RuntimeDirectory=roko-model-asset
RuntimeDirectoryMode=0750
UMask=0027
TimeoutStartSec=15s
NoNewPrivileges=true
PrivateNetwork=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictAddressFamilies=AF_UNIX
CapabilityBoundingSet=
StandardOutput=tty
StandardError=tty
TTYPath=/dev/console
'''.replace('MODEL_BYTES',str(model_bytes))
(stage/'etc/systemd/system/roko-model-asset.service').write_text(unit)
controller=(HERE/'startup_manager_controller.py').read_text()
extra=r'''
 # Delayed actual local asset is independent of successful startup diagnostics.
 ctl('start','roko-model-asset.service')
 assert ctl('show','roko-model-asset.service','--property=ConditionResult','--value').stdout.strip()=='no'
 asset=pathlib.Path('/run/roko-model-asset/status.json');assert not asset.exists()
 print('ROKO_MODEL_DELAY_PHASE '+json.dumps({'phase':'absent-after-startup','system_ready':False}),flush=True)
 import ctypes,uuid
 libc=ctypes.CDLL(None,use_errno=True)
 libc.mount.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_ulong,ctypes.c_char_p];libc.mount.restype=ctypes.c_int
 libc.umount2.argtypes=[ctypes.c_char_p,ctypes.c_int];libc.umount2.restype=ctypes.c_int
 with open('/dev/vda','rb',buffering=0) as disk:
  disk.seek(1128);assert disk.read(16)==uuid.UUID('726f6b6f-6d6f-4465-8000-000000000001').bytes
 def mount_model():
  if libc.mount(b'/dev/vda',b'/opt/roko/models',b'ext4',15,b'noload')!=0:raise OSError(ctypes.get_errno(),'guest read-only mount failed')
 def start_asset(phase):
  ctl('start','roko-model-asset.service');observed=json.loads(asset.read_text())
  assert observed['status']=='asset-observed-not-inference-qualified' and not observed['inference_qualified'] and observed['writer_uid']!=0
  assert observed['bytes']==MODEL_BYTES and not observed['system_ready']
  started=int(ctl('show','roko-model-asset.service','--property=ExecMainStartTimestampMonotonic','--value').stdout.strip())
  diagnostic_exit=int(ctl('show','roko-startup-report.service','--property=ExecMainExitTimestampMonotonic','--value').stdout.strip())
  assert started>diagnostic_exit>0
  assert any('/opt/roko/models' in line and ' ro,' in line for line in pathlib.Path('/proc/mounts').read_text().splitlines())
  print('ROKO_MODEL_DELAY_PHASE '+json.dumps({'phase':phase,'asset':observed,'asset_started_usec':started,'startup_exit_usec':diagnostic_exit,'read_only_mount':True}),flush=True)
 mount_model();start_asset('available-after-startup')
 ctl('stop','roko-model-asset.service');assert not asset.exists()
 assert libc.umount2(b'/opt/roko/models',0)==0
 ctl('start','roko-model-asset.service');assert not asset.exists()
 assert ctl('show','roko-model-asset.service','--property=ConditionResult','--value').stdout.strip()=='no'
 print('ROKO_MODEL_DELAY_PHASE '+json.dumps({'phase':'removed-again','system_ready':False}),flush=True)
 mount_model();start_asset('asset-recovery')
 ctl('restart','roko-startup-report.service');final=json.loads(O.read_text())
 assert final['status']=='unqualified' and not final['system_ready'] and 'model-not-qualified' in final['issues']
 print('ROKO_MODEL_DELAY_FIXTURE_PASS',flush=True)
'''.replace('MODEL_BYTES',str(model_bytes))
controller=controller.replace(" print('ROKO_MANAGER_FIXTURE_PASS',flush=True)",extra+"\n print('ROKO_MANAGER_FIXTURE_PASS',flush=True)")
(stage/'opt/roko/controller.py').write_text(controller)
modroot=next((kernelroot/'usr/lib/modules').iterdir());rows={line.split(':')[0]:line.split(':')[1].split() for line in (modroot/'modules.dep').read_text().splitlines()};order=[]
def visit(name):
 if name in order:return
 for dep in rows[name]:visit(dep)
 order.append(name)
for wanted in ('virtio_blk','crc32c_generic','ext4'):
 found=[n for n in rows if pathlib.Path(n).name.split('.ko')[0]==wanted]
 if len(found)!=1:raise ValueError('required module missing')
 visit(found[0])
(stage/'modules').mkdir()
for i,name in enumerate(order):(stage/'modules'/f'{i}.ko').write_bytes(lzma.decompress((modroot/name).read_bytes()))
source=(base/'init.c').read_text();loads=''
for i in range(len(order)):loads+=f'{{long fd=s(2,(long)"/modules/{i}.ko",0,0,0,0);if(fd<0||s(313,fd,(long)"",0,0,0)<0){{s(60,90,0,0,0,0);for(;;){{}}}}s(3,fd,0,0,0,0);}}'
source=source.replace('s(59,(long)a[0]',loads+'s(59,(long)a[0]');(output/'init.c').write_text(source)
subprocess.run(['gcc',*FLAGS,str(output/'init.c'),'-o',str(stage/'init')],check=True,timeout=30)
records=[]
for i,path in enumerate(sorted(stage.rglob('*')),1):
 name=str(path.relative_to(stage));mode=stat.S_IFDIR|0o755 if path.is_dir() else stat.S_IFREG|(0o555 if path.stat().st_mode&0o111 else 0o444)
 if name=='tmp':mode=stat.S_IFDIR|0o1777
 records.append(baseline.entry(name,b'' if path.is_dir() else path.read_bytes(),mode,i))
for name,major,minor,mode in [('console',5,1,0o600),('null',1,3,0o666),('zero',1,5,0o666),('urandom',1,9,0o666)]:records.append(baseline.entry('dev/'+name,b'',stat.S_IFCHR|mode,len(records)+1,major,minor))
records.append(baseline.entry('TRAILER!!!',b'',0,len(records)+1));raw=b''.join(records);raw+=b'\0'*(-len(raw)%512);image=gzip.compress(raw,mtime=0);(output/'initramfs.gz').write_bytes(image)
result={'sha256':hashlib.sha256(image).hexdigest(),'base_manifest_sha256':hashlib.sha256((base/'manifest.json').read_bytes()).hexdigest(),'delayed_model':{'disk_sha256':model_manifest['model_disk_sha256'],'original_model_sha256':model_manifest['model_sha256'],'model_bytes':model_bytes,'kernel_modules':order},'files':{str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()},'scope':'read-only delayed actual model asset; not inference or Nix image'}
(output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'bytes':len(image),'model_bytes':model_bytes}))
