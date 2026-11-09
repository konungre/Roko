#!/usr/bin/env python3
"""Fail-closed VM gate. Default is a read-only preflight, never an implicit boot."""
import argparse,hashlib,json,subprocess,os,select,time,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BOOT=ROOT/'boot';OUT=ROOT/'build/boot'
def verified_asset(item):
 if type(item) is not dict or set(item)!={'path','sha256'}:raise ValueError('Missing pinned asset')
 path=Path(item['path'])
 if not path.is_absolute() or not path.is_file():raise ValueError('Pinned asset must be an existing absolute file')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Pinned asset digest mismatch')
 return str(path)
def command(qemu,kernel,initramfs):
 return [qemu,'-no-user-config','-nodefaults','-machine','q35,accel=tcg','-m','256','-smp','1','-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot','-kernel',kernel,'-initrd',str(initramfs),'-append','console=ttyS0 rdinit=/init panic=1']
def output_lines(log):
 return {line.strip() for line in re.sub(r'\x1b\[[0-9;]*m','',log).splitlines()}
def boot_passed(log,build_id):
 lines=output_lines(log)
 return any(line.startswith('ROKO_KERNEL ') for line in lines) and ('ROKO_INIT_READY '+build_id) in lines and 'ROKO_INIT_FAILED' not in log
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');exercise=parser.add_mutually_exclusive_group();exercise.add_argument('--exercise-console',action='store_true');exercise.add_argument('--exercise-busybox',action='store_true');exercise.add_argument('--exercise-userland',action='store_true');args=parser.parse_args()
 assets=json.loads((BOOT/'boot-assets.lock.json').read_text());blockers=[]
 paths={}
 for name in ('kernel','qemu'):
  try:paths[name]=verified_asset(assets[name])
  except (ValueError,OSError) as e:blockers.append(name+': '+str(e))
 manifest_path=OUT/'build-manifest.json'
 if not manifest_path.is_file():blockers.append('Build manifest missing')
 else:
  manifest=json.loads(manifest_path.read_text())
  archive=OUT/'roko-initramfs.cpio.gz'
  if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['initramfs_sha256']:blockers.append('Initramfs mismatch')
 if args.run and not blockers:
  integrity=subprocess.run([sys.executable,str(BOOT/'verify-tooling.py')],capture_output=True,text=True,timeout=60)
  (ROOT/'results/boot-runtime-integrity.json').write_text(integrity.stdout+integrity.stderr)
  if integrity.returncode:blockers.append('Extracted QEMU/kernel runtime integrity check failed')
 report={'boot_tested':False,'boot_passed':False,'blockers':blockers,'network_enabled':False,'host_disks_attached':False}
 if blockers or not args.run:
  report['scope']='Preflight only; no VM started'
  (ROOT/'results/boot-vm-status.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(report,indent=2));return 2 if blockers else 0
 cmd=command(paths['qemu'],paths['kernel'],archive)
 if manifest.get('userland_included'):cmd[cmd.index('-m')+1]='512'
 report['memory_mib']=int(cmd[cmd.index('-m')+1])
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 chunks=[];deadline=time.monotonic()+45;reason='timeout';sent=False
 while time.monotonic()<deadline:
  ready,_,_=select.select([proc.stdout],[],[],max(0,min(1,deadline-time.monotonic())))
  if ready:
   chunk=os.read(proc.stdout.fileno(),65536)
   if chunk:chunks.append(chunk)
   elif proc.poll() is not None:reason='exited';break
  partial=b''.join(chunks).decode(errors='replace')
  if args.exercise_console and not sent and 'ROKO_RESCUE_READY' in partial:
   proc.stdin.write(b'x'*200+b'\nnot-a-command\nstatus\nhelp\npoweroff\n');proc.stdin.flush();sent=True
  if args.exercise_busybox and not sent and 'ROKO_BUSYBOX_PRESENT' in partial:
   proc.stdin.write(b"set -e; echo ROKO_BUSYBOX_READY; /bin/busybox uname -r; echo roko-userland >/tmp/roko-check; /bin/busybox cat /tmp/roko-check; echo ROKO_BUSYBOX_CHECK_PASSED; /bin/busybox poweroff -f\n");proc.stdin.flush();sent=True
  if args.exercise_userland and not sent and 'ROKO_BUSYBOX_PRESENT' in partial:
   proc.stdin.write(b"set -e; export PYTHONHOME=/opt/roko/python; export PATH=/bin; /opt/roko/python/bin/python3.12 /opt/roko/guest-smoke.py; /bin/busybox poweroff -f\n");proc.stdin.flush();sent=True
  if not (args.exercise_console or args.exercise_busybox or args.exercise_userland) and boot_passed(partial,manifest['build_id']):
   reason='ready marker';break
  if proc.poll() is not None:reason='exited';break
 if proc.poll() is None:proc.terminate()
 try:tail=proc.communicate(timeout=5)[0]
 except subprocess.TimeoutExpired:proc.kill();tail=proc.communicate()[0]
 output=b''.join(chunks)+tail
 report['stop_reason']=reason
 log=output.decode(errors='replace');(ROOT/'results/boot-serial.txt').write_text(log)
 report.update({'boot_tested':True,'boot_passed':boot_passed(log,manifest['build_id']),'qemu_returncode':proc.returncode,'kernel_sha256':assets['kernel']['sha256'],'qemu_launcher_sha256':assets['qemu']['sha256'],'initramfs_sha256':manifest['initramfs_sha256'],'scope':'CPU-emulated restricted serial rescue; not COSMIC or Roko cognitive runtime'})
 (ROOT/'results/boot-vm-status.json').write_text(json.dumps(report,indent=2)+'\n')
 if args.exercise_console:
  report['console_exercised']=sent
  report['console_passed']=sent and all(marker in log for marker in ['ROKO_COMMAND_REJECTED too long','ROKO_COMMAND_REJECTED unknown command','ROKO_STATUS serial-rescue','ROKO_HELP help status poweroff','ROKO_GUEST_POWER_OFF','Power down']) and proc.returncode==0
  (ROOT/'results/boot-vm-status.json').write_text(json.dumps(report,indent=2)+'\n')
 if args.exercise_busybox:
  report['busybox_exercised']=sent
  report['busybox_passed']=sent and all(marker in output_lines(log) for marker in ['ROKO_BUSYBOX_READY','roko-userland','ROKO_BUSYBOX_CHECK_PASSED']) and 'Power down' in log and proc.returncode==0
  (ROOT/'results/boot-vm-status.json').write_text(json.dumps(report,indent=2)+'\n')
 if args.exercise_userland:
  report['scope']='CPU-emulated BusyBox, Roko controller, PeTTa, Janus and upstream Omega message-state primitives; no COSMIC, model or autonomy'
  report['userland_exercised']=sent
  report['userland_passed']=sent and all(marker in output_lines(log) for marker in ['ROKO_GUEST_REJECTION_PASSED','ROKO_GUEST_MODEL_FAIL_CLOSED','ROKO_GUEST_PETTA_ARITHMETIC_PASSED result=56','ROKO_GUEST_JANUS_PASSED result=42','ROKO_GUEST_OMEGA_MESSAGES_PASSED counts=0,1,0','ROKO_GUEST_CONTROLLER_PASSED']) and 'Power down' in log and proc.returncode==0
  for line in log.splitlines():
   if line.startswith('ROKO_GUEST_STATE '):report['guest_controller_state']=json.loads(line[len('ROKO_GUEST_STATE '):])
  (ROOT/'results/boot-vm-status.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2));return 0 if report['boot_passed'] and report.get('console_passed',True) and report.get('busybox_passed',True) and report.get('userland_passed',True) else 1
if __name__=='__main__':raise SystemExit(main())
