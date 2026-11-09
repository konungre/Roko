"""Bounded no-network TCG fixture; optional held read-only regular-file model disk."""
import sys,pathlib,json,subprocess,os,time,selectors,hashlib
import argparse,atexit,stat
parser=argparse.ArgumentParser();parser.add_argument('runtime');parser.add_argument('lock');parser.add_argument('guest');parser.add_argument('output');parser.add_argument('--model-disk');args=parser.parse_args()
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));from run_probe import verify_runtime
from startup_manager_evidence import parse
runtime=pathlib.Path(args.runtime).resolve();verification=verify_runtime(runtime,pathlib.Path(args.lock).resolve());lib=runtime/'usr/lib/x86_64-linux-gnu';root=pathlib.Path(args.guest).resolve();image=root/'initramfs.gz';out=pathlib.Path(args.output).resolve();out.mkdir(mode=0o700)
image_hash=hashlib.sha256(image.read_bytes()).hexdigest();manifest=json.loads((root/'manifest.json').read_text())
if image_hash!=manifest['sha256']:raise ValueError('guest image changed')
available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
if available<2560*1024**2:raise ValueError('insufficient bounded guest headroom')
cmd=[str(lib/'ld-linux-x86-64.so.2'),'--library-path',str(lib),str(runtime/'usr/bin/qemu-system-x86_64'),'-L',str(runtime/'usr/share/qemu'),'-bios',str(runtime/'usr/share/seabios/bios-256k.bin'),'-no-user-config','-nodefaults','-machine','q35,accel=tcg','-m','512','-smp','1','-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot','-kernel',str(next((runtime/'boot').glob('vmlinuz-*'))),'-initrd',str(image),'-append','console=ttyS0 rdinit=/init panic=1']
disk_fd=None
if manifest.get('delayed_model'):
 if not args.model_disk:raise ValueError('explicit read-only model disk required')
 disk_fd=os.open(args.model_disk,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);atexit.register(os.close,disk_fd)
 info=os.fstat(disk_fd)
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('regular single-link fixture disk required')
 digest=hashlib.sha256();offset=0
 while block:=os.pread(disk_fd,4*1024**2,offset):digest.update(block);offset+=len(block)
 after=os.fstat(disk_fd)
 if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or digest.hexdigest()!=manifest['delayed_model']['disk_sha256']:raise ValueError('model disk mismatch')
 cmd+=['-drive',f'if=none,id=model,format=raw,readonly=on,file=/proc/self/fd/{disk_fd}','-device','virtio-blk-pci,drive=model']
elif args.model_disk:raise ValueError('unexpected model disk')
start=time.monotonic();p=subprocess.Popen(cmd,pass_fds=(() if disk_fd is None else (disk_fd,)),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env={'PATH':'/usr/bin:/bin','LANG':'C','QEMU_MODULE_DIR':str(lib/'qemu')});data=bytearray();stop='eof'
try:
 with selectors.DefaultSelector() as sel:
  sel.register(p.stdout,selectors.EVENT_READ)
  while True:
   if time.monotonic()-start>110:stop='timeout';break
   if not sel.select(.25):continue
   block=os.read(p.stdout.fileno(),65536)
   if not block:break
   data.extend(block)
   with (out/'serial.txt').open('ab') as stream:stream.write(block)
   if len(data)>2*1024**2:stop='output-limit';break
finally:
 if p.poll() is None:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
 p.stdout.close()
(out/'serial.txt').write_bytes(data);text=data.decode(errors='replace');report={'command':cmd,'runtime':verification,'image_sha256':image_hash,'serial_sha256':hashlib.sha256(data).hexdigest(),'manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),'passed':stop=='eof' and p.returncode==0 and text.count('ROKO_MANAGER_FIXTURE_PASS')==1 and 'ROKO_MANAGER_FIXTURE_FAIL' not in text,'stop':stop,'returncode':p.returncode,'elapsed_seconds':time.monotonic()-start,'child_reaped':p.poll() is not None,'network_device':False,'host_disks':False,'fixture_model_disk_read_only':disk_fd is not None,'host_activation':False,'scope':'adapted Debian systemd service-manager fixture, not Nix image'};
try:
 report['serial_contract']=parse(bytes(data))
 if manifest.get('delayed_model'):
  from startup_manager_evidence import parse_model_delay
  report['delayed_model_contract']=parse_model_delay(bytes(data),manifest['delayed_model']['model_bytes'])
  report['model_disk_sha256']=manifest['delayed_model']['disk_sha256']
except (ValueError,KeyError,TypeError) as error:report['passed']=False;report['serial_contract_error']=str(error)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
