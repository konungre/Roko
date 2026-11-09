#!/usr/bin/env python3
"""Explicit creation and two-boot test of a fixed private image. Default preflight only."""
import argparse
import gzip
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import tempfile
import time
import build
from image import open_image, attach, UUID

ROOT=build.ROOT
OUT=build.OUT

def create():
    import formatter
    formatter.verify()  # Fail before exclusive creation if tooling is unavailable.
    fd=open_image(ROOT,create=True)
    report={'formatted':False,'filesystem_checked':False}
    try:
        provenance,output=formatter.execute('mke2fs',fd,format_image=True)
        os.fsync(fd)
        report.update(provenance,formatted=True,formatter_output=output)
        _,check=formatter.execute('e2fsck',fd)
        _,header=formatter.execute('dumpe2fs',fd)
        report.update(filesystem_checked=True,fsck_output=check,superblock=header)
    finally:
        os.close(fd)
        (OUT/'format-receipt.json').write_text(json.dumps(report,indent=2)+'\n')

def preflight():
    assets,kernel,_,modules,order,sources=build.inputs()
    manifest=json.loads((OUT/'manifest.json').read_text()); data=(OUT/'controller.cpio.gz').read_bytes()
    if build.sha(data)!=manifest['initramfs_sha256'] or build.archive.inspect(gzip.decompress(data))!=manifest['entries']: raise ValueError('Archive mismatch')
    if sources!=manifest['sources'] or modules!=manifest['modules'] or order!=manifest['module_order'] or kernel!=manifest['kernel_release']: raise ValueError('Inputs changed; rebuild')
    for name,digest in manifest['controller'].items():
        if build.sha((ROOT/name).read_bytes())!=digest: raise ValueError('Controller source changed; rebuild')
    if build.sha(build.BASE.read_bytes())!=manifest['base_archive_sha256'] or build.sha(build.BASE_MANIFEST.read_bytes())!=manifest['base_manifest_sha256']: raise ValueError('Released userland changed')
    for name,digest in manifest['scripts'].items():
        if build.sha((build.HERE/name).read_bytes())!=digest: raise ValueError('Source changed; rebuild')
    return assets,manifest

def boot(fd,assets,manifest,phase):
    cmd=build.vm.command(assets['qemu']['path'],assets['kernel']['path'],OUT/'controller.cpio.gz')
    cmd[cmd.index('-append')+1]+=' roko.controller='+phase
    cmd[cmd.index('-m')+1]='512'
    cmd+=attach(fd)
    proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,pass_fds=(fd,))
    chunks=[]; size=0; reason='timeout'; end=time.monotonic()+120
    try:
        while time.monotonic()<end:
            if select.select([proc.stdout],[],[],.2)[0]:
                chunk=os.read(proc.stdout.fileno(),65536)
                if not chunk: reason='exited'; break
                chunks.append(chunk); size+=len(chunk)
                if size>2*1024*1024: reason='output limit'; break
    finally:
        if proc.poll() is None:
            try: proc.wait(timeout=1)
            except subprocess.TimeoutExpired: proc.terminate()
        try: tail=proc.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired: proc.kill(); tail=proc.communicate(timeout=5)[0]
    log=(b''.join(chunks)+tail).decode(errors='replace'); lines=build.vm.output_lines(log)
    marker=f'ROKO_EXT4_CONTROLLER_{phase.upper()}_PASSED tasks=2 revisions=7,2 actions=0'
    passed=reason=='exited' and proc.returncode==0 and marker in lines and 'ROKO_EXT4_CONTROLLER_BUILD '+manifest['build_id'] in lines and 'ROKO_EXT4_CONTROLLER_UNMOUNTED' in lines and 'Power down' in log and 'ROKO_EXT4_CONTROLLER_FAILED' not in log
    if phase=='write': passed &= 'ROKO_EXT4_CONTROLLER_REJECTION_PASSED' in lines
    return log,{'phase':phase,'passed':passed,'qemu_returncode':proc.returncode,'stop_reason':reason}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(); group.add_argument('--create',action='store_true'); group.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.create: create(); print('Created private 64 MiB ext4 image; no VM started'); return 0
    assets,manifest=preflight()
    fd=open_image(ROOT)
    try:
        # ext4 magic and fixed UUID, through the already admitted descriptor.
        import uuid
        if os.pread(fd,2,1080)!=b'\x53\xef' or os.pread(fd,16,1128)!=uuid.UUID(UUID).bytes: raise ValueError('Wrong filesystem identity')
        if not args.run: print('Preflight passed; no VM started'); return 0
        subprocess.run(['python3',str(ROOT/'boot/verify-tooling.py')],check=True,timeout=60)
        results=ROOT/'results/cognitive-filesystem-guest'; results.mkdir(exist_ok=True)
        attempt=Path(tempfile.mkdtemp(prefix='attempt-',dir=results))
        report={'passed':False,'phases':[],'network_enabled':False,'host_disks_attached':False,'private_image_bytes':64*1024*1024,'memory_mib':512,'cpus':1,'per_boot_timeout_seconds':120,'build_id':manifest['build_id'],'scope':'Actual Roko CLI/StateStore on ext4; clean two-boot recovery, no inference/autonomy/action dispatch or power-loss guarantee'}
        for phase in ['write','read']:
            log,result=boot(fd,assets,manifest,phase); (attempt/(phase+'-serial.txt')).write_text(log); report['phases'].append(result)
            if not result['passed']: break
        report['passed']=len(report['phases'])==2 and all(x['passed'] for x in report['phases'])
        if report['passed']:
            import formatter
            try:
                provenance,check=formatter.execute('e2fsck',fd)
                report.update(formatter_provenance=provenance,post_boot_fsck_passed=True)
                (attempt/'post-boot-fsck.txt').write_text(check)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                report.update(passed=False,post_boot_fsck_passed=False,post_boot_fsck_error=str(exc))
        (attempt/'validation.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); print('Evidence: '+str(attempt))
        return 0 if report['passed'] else 1
    finally: os.close(fd)
if __name__=='__main__': raise SystemExit(main())
