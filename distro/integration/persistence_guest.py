#!/usr/bin/env python3
"""Two cold boots verify non-root private state on a disposable ext4 disk.

Uses an existing verified model capsule only for its kernel modules/Python.
No model inference or COSMIC claim is made by this storage qualification.
"""
import argparse,gzip,hashlib,json,os,shutil,stat,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_probe import baseline,FLAGS
from run_probe import verify_runtime
from probe_gate import serial_evidence

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(capsule,runtime,lock,tools,out):
 capsule,runtime,lock,tools,out=map(Path,(capsule,runtime,lock,tools,out))
 verify_runtime(runtime,lock)
 manifest=json.loads((capsule/'manifest.json').read_text())
 if sha(capsule/'init.c')!=manifest['source_sha256']:raise ValueError('Source changed')
 if sha(capsule/'initramfs.cpio.gz')!=manifest['initramfs_sha256']:raise ValueError('Capsule changed')
 out.mkdir(mode=0o700)
 # Reuse the inspected archive entries, not mutable staging directories.
 raw=gzip.decompress((capsule/'initramfs.cpio.gz').read_bytes())
 baseline.inspect(raw)
 source=(capsule/'init.c').read_text()
 start=source.index(' {unsigned char id[16]=')
 end=source.index(' long child=sc(57,',start)
 source=source[:start]+''' if(sc(83,(long)"/state",0700,0,0,0,0)<0){stop();}
 if(sc(165,(long)"/dev/vda",(long)"/state",(long)"ext4",6,0,0)<0){say(1,"STATE_MOUNT_FAILED\\n");stop();}
 if(sc(92,(long)"/state",1000,1000,0,0,0)<0 || sc(90,(long)"/state",0700,0,0,0,0)<0){stop();}
'''+source[end:]
 source=source.replace('"/opt/roko/guest_driver.py"','"/state_probe.py"')
 source=source.replace(' say(1,"ROKO_FOUNDATION_COMPLETE ', ' sc(162,0,0,0,0,0,0);\n if(sc(166,(long)"/state",0,0,0,0,0)<0){say(1,"STATE_UNMOUNT_FAILED\\n");stop();}\n say(1,"ROKO_FOUNDATION_COMPLETE ')
 driver='''import os,json,stat
from pathlib import Path
assert os.getresuid()==(1000,1000,1000)
p=Path('/state'); assert stat.S_IMODE(p.stat().st_mode)==0o700
f=p/'session.json'
if f.exists():
 assert f.read_text()=='{"turn":1}\\n'
 assert f.stat().st_uid==1000 and stat.S_IMODE(f.stat().st_mode)==0o600
 phase='restored'
else:
 fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 os.write(fd,b'{"turn":1}\\n');os.fsync(fd);os.close(fd)
 fd=os.open(p,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 phase='created'
print('ROKO_STATE_PASSED '+json.dumps({'phase':phase,'uid':os.getuid()}),flush=True)
'''
 buildid=hashlib.sha256((source+driver).encode()).hexdigest()
 (out/'init.c').write_text(source)
 subprocess.run(['gcc',*FLAGS,'-DROKO_BUILD_ID="'+buildid+'"',str(out/'init.c'),'-o',str(out/'init')],check=True)
 # Preserve measured archive entries except init, and append the probe.
 pos=0;records=[]
 while True:
  header=raw[pos:pos+110];fields=[int(header[i:i+8],16) for i in range(6,110,8)]
  size,namesize=fields[6],fields[11];name=raw[pos+110:pos+110+namesize-1].decode()
  data_start=(pos+110+namesize+3)&~3;end=(data_start+size+3)&~3
  if name=='TRAILER!!!':break
  if name!='init':records.append(raw[pos:end])
  pos=end
 records += [baseline.entry('init',(out/'init').read_bytes(),stat.S_IFREG|0o555,90001),baseline.entry('state_probe.py',driver.encode(),stat.S_IFREG|0o444,90002),baseline.entry('TRAILER!!!',b'',0,90003)]
 packed=b''.join(records);packed+=b'\0'*(-len(packed)%512);baseline.inspect(packed)
 initrd=out/'initramfs.cpio.gz';initrd.write_bytes(gzip.compress(packed,compresslevel=6,mtime=0))
 disk=out/'state.img'
 with disk.open('xb') as f:f.truncate(64*1024**2)
 disk.chmod(0o600)
 env={**os.environ,'LD_LIBRARY_PATH':str(tools/'usr/lib/x86_64-linux-gnu'),'MKE2FS_CONFIG':str(tools/'etc/mke2fs.conf')}
 subprocess.run([str(tools/'usr/sbin/mke2fs'),'-q','-F','-t','ext4',str(disk)],env=env,check=True)
 lib=runtime/'usr/lib/x86_64-linux-gnu'
 cmd=[str(lib/'ld-linux-x86-64.so.2'),'--library-path',str(lib),str(runtime/'usr/bin/qemu-system-x86_64'),'-L',str(runtime/'usr/share/qemu'),'-bios',str(runtime/'usr/share/seabios/bios-256k.bin'),'-no-user-config','-nodefaults','-machine','q35,accel=tcg','-m','1024','-smp','1','-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot','-kernel',str(next((runtime/'boot').glob('vmlinuz-*'))),'-initrd',str(initrd),'-append','console=ttyS0 rdinit=/init panic=1','-drive','if=none,id=state,format=raw,file='+str(disk),'-device','virtio-blk-pci,drive=state']
 rows=[]
 for phase in ('created','restored'):
  result=subprocess.run(cmd,capture_output=True,timeout=60,env={**env,'QEMU_MODULE_DIR':str(lib/'qemu')})
  log=result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace');(out/(phase+'.serial')).write_text(log)
  passed=serial_evidence(log,buildid,result.returncode)['serial_contract_passed'] and ('"phase": "'+phase+'"') in log
  rows.append({'phase':phase,'passed':passed,'returncode':result.returncode,'serial_sha256':sha(out/(phase+'.serial'))})
  if not passed:break
 report={'schema':'roko-private-state-coldboot-v1','passed':len(rows)==2 and all(r['passed'] for r in rows),'boots':rows,'initramfs_sha256':sha(initrd),'state_sha256':sha(disk),'cosmic_tested':False,'model_tested':False,'network':False}
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('capsule','runtime','lock','tools','output'):p.add_argument(n)
 a=p.parse_args();r=run(a.capsule,a.runtime,a.lock,a.tools,a.output);print(json.dumps(r));sys.exit(0 if r['passed'] else 1)
