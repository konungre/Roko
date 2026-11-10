"""Assemble an adapted Debian systemd VM fixture from trusted local inputs only."""
import sys,pathlib,shutil,subprocess,os,re,stat,gzip,json,hashlib
import argparse
parser=argparse.ArgumentParser();parser.add_argument('symbolic');parser.add_argument('unit_evaluation');parser.add_argument('output');args=parser.parse_args()
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'distro'))
from build_probe import baseline,FLAGS
root=pathlib.Path(args.output).resolve();root.mkdir();stage=root/'root';stage.mkdir()
for directory in ('etc/systemd/system','etc/roko','proc','sys','dev','run','tmp','var','usr/bin','usr/lib/systemd','lib64','home'):(stage/directory).mkdir(parents=True,exist_ok=True)
(stage/'tmp').chmod(0o1777)
provenance={}
def copy(src,dest=None):
 src=pathlib.Path(src);dest=stage/str(dest or src).lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);provenance[str(dest.relative_to(stage))]=str(src.resolve());return dest
native=[]
for src in ['/usr/lib/systemd/systemd','/usr/lib/systemd/systemd-executor','/usr/bin/systemctl','/usr/bin/echo']:
 native.append(copy(src))
# Preserve host systemd shared-library location and its complete ldd closure.
for obj in list(native):
 r=subprocess.run(['ldd',str(obj)],capture_output=True,text=True,check=True);assert 'not found' not in r.stdout
 for path in re.findall(r'(?:=>\s+)?(/\S+)\s+\(',r.stdout):copy(path)
profile=json.loads((pathlib.Path(args.symbolic).resolve()/'symbolic-profile.json').read_text());pyhome=pathlib.Path(profile['runtime_env']['PYTHONHOME']);python=pathlib.Path(profile['python']).resolve()
copy(python,'opt/python/bin/python3')
ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','ensurepip','tkinter','idlelib','turtledemo','*.pyc')
shutil.copytree(pyhome/'lib/python3.12',stage/'opt/python/lib/python3.12',ignore=ignore)
for p in (pyhome/'lib').glob('libpython3.12.so*'):copy(p,'opt/python/lib/'+p.name)
env={**os.environ,'LD_LIBRARY_PATH':str(pyhome/'lib')}
for obj in [python,*list((stage/'opt/python').rglob('*.so'))]:
 r=subprocess.run(['ldd',str(obj)],env=env,capture_output=True,text=True);assert 'not found' not in r.stdout,r.stdout
 for path in re.findall(r'(?:=>\s+)?(/\S+)\s+\(',r.stdout):
  if not pathlib.Path(path).is_relative_to(stage):copy(path)
copy(repo/'distro/nix/startup_report.py','opt/roko/startup_report.py');copy(repo/'distro/nix/memory_budget.py','opt/roko/memory_budget.py');copy(repo/'distro/integration/startup_manager_controller.py','opt/roko/controller.py')
(stage/'etc/roko-service-manager-fixture').write_text('roko-disposable-service-manager-v1\n')
(stage/'etc/passwd').write_text('root:x:0:0:root:/root:/bin/false\nnobody:x:65534:65534:nobody:/:/bin/false\n');(stage/'etc/group').write_text('root:x:0:\nnogroup:x:65534:\n');(stage/'etc/os-release').write_text('ID=roko-test\nNAME="Roko systemd fixture"\n');(stage/'etc/machine-id').write_text('00000000000000000000000000000001\n')
unit=pathlib.Path(args.unit_evaluation).resolve();values=json.loads(unit.read_text())
text=re.sub(r'^Environment=.*$','',values['unit'],flags=re.M);text=re.sub(r'^ExecStart=.*$', 'ExecStart=/opt/python/bin/python3 /opt/roko/startup_report.py --policy /etc/roko/first-boot.json --output /run/roko-startup/status.json',text,flags=re.M)
text+='\n[Service]\nEnvironment=PYTHONHOME=/opt/python\nEnvironment=LD_LIBRARY_PATH=/opt/python/lib\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nStandardOutput=tty\nStandardError=tty\nTTYPath=/dev/console\n'
(stage/'etc/systemd/system/roko-startup-report.service').write_text(text)
fail=re.sub(r'^Environment=.*$','',values['failureUnit'],flags=re.M);fail=re.sub(r'^ExecStart=.*$', 'ExecStart=/usr/bin/echo Roko startup diagnostic failed; readiness unknown',fail,flags=re.M);fail+='\n[Service]\nStandardOutput=tty\nStandardError=tty\nTTYPath=/dev/console\n';(stage/'etc/systemd/system/roko-startup-report-failure.service').write_text(fail)
(stage/'etc/systemd/system/roko-fixture.target').write_text('[Unit]\nDefaultDependencies=no\nWants=roko-fixture-run.service\n')
(stage/'etc/systemd/system/roko-fixture-run.service').write_text('[Unit]\nDefaultDependencies=no\n[Service]\nType=oneshot\nExecStart=/opt/python/bin/python3 /opt/roko/controller.py\nEnvironment=PYTHONHOME=/opt/python\nEnvironment=LD_LIBRARY_PATH=/opt/python/lib\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nStandardOutput=tty\nStandardError=tty\nTTYPath=/dev/console\nTimeoutStartSec=90s\n')
# Minimal target dependencies exist solely in this service-manager fixture.
for name in ['sysinit.target','basic.target','local-fs.target','shutdown.target','multi-user.target']:(stage/'etc/systemd/system'/name).write_text('[Unit]\nDefaultDependencies=no\n')
init='''static long s(long n,long a,long b,long c,long d,long e){register long r10 __asm__("r10")=d,r8 __asm__("r8")=e;long r;__asm__ volatile("syscall":"=a"(r):"a"(n),"D"(a),"S"(b),"d"(c),"r"(r10),"r"(r8):"rcx","r11","memory");return r;}void _start(void){s(165,(long)"proc",(long)"/proc",(long)"proc",0,0);s(165,(long)"sysfs",(long)"/sys",(long)"sysfs",0,0);s(165,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",0,0);s(165,(long)"tmpfs",(long)"/run",(long)"tmpfs",0,0);s(83,(long)"/sys/fs/cgroup",0755,0,0,0);s(165,(long)"cgroup2",(long)"/sys/fs/cgroup",(long)"cgroup2",0,0);char *a[]={"/usr/lib/systemd/systemd","--system","--unit=roko-fixture.target","--log-target=console",0};char *e[]={"PATH=/usr/bin","SYSTEMD_UNIT_PATH=/etc/systemd/system","SYSTEMD_LOG_COLOR=0","SYSTEMD_LOG_LEVEL=debug","SYSTEMD_IN_INITRD=0",0};s(59,(long)a[0],(long)a,(long)e,0,0);s(60,99,0,0,0,0);for(;;){}}'''
(root/'init.c').write_text(init);subprocess.run(['gcc',*FLAGS,str(root/'init.c'),'-o',str(stage/'init')],check=True)
records=[]
for i,p in enumerate(sorted(stage.rglob('*')),1):
 name=str(p.relative_to(stage));mode=stat.S_IFDIR|0o755 if p.is_dir() else stat.S_IFREG|(0o555 if p.stat().st_mode&0o111 else 0o444)
 if name=='tmp':mode=stat.S_IFDIR|0o1777
 records.append(baseline.entry(name,b'' if p.is_dir() else p.read_bytes(),mode,i))
for name,major,minor,mode in [('console',5,1,0o600),('null',1,3,0o666),('zero',1,5,0o666),('urandom',1,9,0o666)]:records.append(baseline.entry('dev/'+name,b'',stat.S_IFCHR|mode,len(records)+1,major,minor))
records.append(baseline.entry('TRAILER!!!',b'',0,len(records)+1));raw=b''.join(records);raw+=b'\0'*(-len(raw)%512);data=gzip.compress(raw,mtime=0);(root/'initramfs.gz').write_bytes(data)
(root/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'unit_evaluation_sha256':hashlib.sha256(unit.read_bytes()).hexdigest(),'files':{str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()},'host_copied_inputs':provenance,'scope':'adapted systemd guest fixture; not Nix image'},indent=2)+'\n');print(len(data))
