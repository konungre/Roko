#!/usr/bin/env python3
"""Explicit coordinated root population, complete readback verification and tiny bootstrap."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import bootstrap
import image
import plan
import source
import tooling
import verify

ROOT=plan.ROOT
OUT=ROOT/'build/disk-root-guest'

def hash_fd(fd):
    h=hashlib.sha256();offset=0
    while True:
        data=os.pread(fd,4*1024**2,offset)
        if not data:break
        h.update(data);offset+=len(data)
    return h.hexdigest()

def build():
    proof=json.loads((ROOT/'build/disk-root-capability-probe/validation.json').read_text())
    if not proof.get('passed') or not proof.get('stdin_tar_proved') or not proof.get('root_guest_ownership_proved'):raise ValueError('Actual stdin tar ownership probe required')
    current=tooling.verify()
    if any(proof['tooling'][k]!=current[k] for k in ['stage_files_lock_sha256','stage_packages_lock_sha256','libarchive_source_lock_sha256','libarchive_sources']):raise ValueError('Tooling changed since capability proof')
    budget=plan.summary()
    if not budget['streaming_space_budget_passed']:raise ValueError('Root would violate four GiB free reserve')
    fd=image.open_image(ROOT,create=True);started=time.monotonic();report={'passed':False,'format_started':True,'space_before':budget}
    try:
        with tooling.descriptors('mke2fs') as (cmd,fds,env,receipt), (OUT/'format-stdout.txt').open('xb') as stdout,(OUT/'format-stderr.txt').open('xb') as stderr:
            proc=subprocess.Popen(cmd+tooling.format_args(fd,'root'),stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,env=env,pass_fds=(*fds,fd))
            timer=threading.Timer(600,lambda:proc.kill() if proc.poll() is None else None);timer.start()
            try:
                source_manifest=source.write_source(proc.stdin)
                proc.stdin.close();proc.wait(timeout=120)
                if proc.returncode:raise ValueError('Root formatter failed: '+str(proc.returncode))
            finally:
                timer.cancel()
                if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        os.fsync(fd)
        with (OUT/'root-source.json').open('x') as stream:json.dump(source_manifest,stream,indent=2);stream.write('\n')
        report.update(formatted=True,build_id=source_manifest['build_id'],source_tar_sha256=source_manifest['source_tar_sha256'],source_tar_bytes=source_manifest['source_tar_bytes'],tooling=receipt)
    except BaseException:
        with (OUT/'failed-population.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        raise
    finally:os.close(fd)
    print('Root streamed/formatted; no retained tar. Starting full ownership and payload readback.',flush=True)
    fd=image.open_image(ROOT)
    try:
        checks=verify.verify_image(fd,source_manifest,lambda msg:print(msg,flush=True))
        with (OUT/'readback.json').open('x') as stream:json.dump(checks,stream,indent=2);stream.write('\n')
        _,fsck=tooling.formatter.execute('e2fsck',fd)
        (OUT/'fsck.txt').write_text(fsck)
        report.update(root_sha256=hash_fd(fd),logical_bytes=os.fstat(fd).st_size,allocated_bytes=os.fstat(fd).st_blocks*512,
                      verified_entries=checks['verified_entries'],verified_payloads=checks['verified_payloads'],fsck_passed=True)
    finally:os.close(fd)
    boot=bootstrap.build()
    report.update(passed=True,bootstrap_sha256=boot['initramfs_sha256'],bootstrap_bytes=boot['initramfs_bytes'],bootstrap_uncompressed_bytes=boot['uncompressed_bytes'],free_bytes_after=shutil.disk_usage(ROOT).free,elapsed_seconds=round(time.monotonic()-started,3),boot_tested=False)
    if report['free_bytes_after']<plan.RESERVE_BYTES:raise ValueError('Four GiB reserve breached')
    with (OUT/'validation.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    return {k:report[k] for k in ['passed','build_id','root_sha256','logical_bytes','allocated_bytes','verified_entries','verified_payloads','bootstrap_bytes','free_bytes_after','elapsed_seconds','boot_tested']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');args=p.parse_args()
    print(json.dumps(build() if args.build else plan.summary(),indent=2))
