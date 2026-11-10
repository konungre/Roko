#!/usr/bin/env python3
"""Finite 10 GiB TCG conversation guest with two held read-only image descriptors."""
import argparse,hashlib,json,os,select,stat,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_probe import verify_runtime
from probe_gate import serial_evidence
from memory_budget import admit,observe

def digest(fd):
    h=hashlib.sha256();offset=0
    while block:=os.pread(fd,4*1024**2,offset):h.update(block);offset+=len(block)
    return h.hexdigest()

def available():
    return next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))

def run(guest,runtime,lock,output):
    guest,runtime,lock,output=map(Path,(guest,runtime,lock,output));verify_runtime(runtime,lock)
    memory_admission=admit(10240,reserve_mib=2048)
    manifest=json.loads((guest/'manifest.json').read_text());fds={};proc=None;serial_file=None
    output.mkdir(mode=0o700)
    try:
        for name,field in [('workspace.img','workspace_sha256'),('model.img','model_disk_sha256'),('initramfs.cpio.gz','initramfs_sha256')]:
            fd=os.open(guest/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);fds[name]=fd
            if not stat.S_ISREG(os.fstat(fd).st_mode) or digest(fd)!=manifest[field]:raise ValueError('Guest asset mismatch')
        lib=runtime/'usr/lib/x86_64-linux-gnu';kernel=next((runtime/'boot').glob('vmlinuz-*'))
        path=lambda name:f'/proc/self/fd/{fds[name]}'
        command=[str(lib/'ld-linux-x86-64.so.2'),'--inhibit-cache','--library-path',str(lib),str(runtime/'usr/bin/qemu-system-x86_64'),'-L',str(runtime/'usr/share/qemu'),'-bios',str(runtime/'usr/share/seabios/bios-256k.bin'),'-no-user-config','-nodefaults','-machine','q35','-accel','tcg,thread=multi','-cpu','max','-m','10240','-smp','4','-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot','-kernel',str(kernel),'-initrd',path('initramfs.cpio.gz'),'-append','console=ttyS0 rdinit=/init panic=1']
        for name,ident in [('workspace.img','source'),('model.img','model')]:command+=['-drive',f'if=none,id={ident},format=raw,readonly=on,file='+path(name),'-device','virtio-blk-pci,drive='+ident]
        memory_admission=admit(10240,reserve_mib=2048)
        admission={'memory_admission':memory_admission,'manifest':manifest,'guest_memory_mib':10240,'cpus':4,'deadline_seconds':600,'host_memory_floor_gib':2,'qemu_rss_limit_gib':12,'network':False,'disks_read_only':True,'iso_used':False,'command':command}
        (output/'admission.json').write_text(json.dumps(admission,indent=2)+'\n')
        proc=subprocess.Popen(command,pass_fds=tuple(fds.values()),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env={'PATH':'/usr/bin:/bin','LANG':'C','QEMU_MODULE_DIR':str(lib/'qemu')})
        serial_file=(output/'serial.txt').open('xb')
        data=bytearray();start=time.monotonic();stop='eof'
        while True:
            if time.monotonic()-start>600:stop='deadline';break
            if observe()['observed_headroom_bytes']<2*1024**3:stop='observed-host-cgroup-memory-floor';break
            try:
                lines=Path(f'/proc/{proc.pid}/status').read_text().splitlines();rss=next((int(l.split()[1])*1024 for l in lines if l.startswith('VmRSS:')),0)
                if rss>12*1024**3:stop='qemu-rss-limit';break
            except FileNotFoundError:pass
            if select.select([proc.stdout],[],[],.25)[0]:
                chunk=os.read(proc.stdout.fileno(),65536)
                if not chunk:break
                serial_file.write(chunk);serial_file.flush()
                data.extend(chunk)
                if len(data)>2*1024**2:stop='output-limit';break
        if proc.poll() is None and stop!='eof':proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait();stop='kill-after-timeout'
        serial_file.close();serial_file=None
        log=data.decode(errors='replace')
        rows=[json.loads(l.removeprefix('ROKO_GUEST_CONVERSATION_PASSED ')) for l in log.replace('\r\n','\n').splitlines() if l.startswith('ROKO_GUEST_CONVERSATION_PASSED ')]
        native=serial_evidence(log,manifest['build_id'],proc.returncode)
        passed=stop=='eof' and native['serial_contract_passed'] and len(rows)==1 and rows[0]['uid']==1000 and rows[0]['model_identity_unchanged']
        result={'schema':'roko-real-conversation-guest-v1','passed':passed,'returncode':proc.returncode,'stop_reason':stop,'seconds':time.monotonic()-start,'child_reaped':True,'response_evidence':rows,'serial_sha256':hashlib.sha256(data).hexdigest(),'network':False,'read_only_disks':True,'cosmic_tested':False,'scope':'One actual bounded non-root model conversation request in an independent minimal guest'}
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
    finally:
        if proc is not None and proc.poll() is None:proc.kill();proc.wait(timeout=5)
        if proc is not None:proc.stdout.close()
        if serial_file is not None:serial_file.close()
        for fd in fds.values():os.close(fd)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('guest','runtime','lock','output'):p.add_argument(n,type=Path)
    a=p.parse_args();r=run(a.guest,a.runtime,a.lock,a.output);print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 1)
