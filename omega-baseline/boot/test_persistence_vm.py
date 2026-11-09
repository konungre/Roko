#!/usr/bin/env python3
"""Opt-in two-boot persistence probe. Default only validates, never starts a VM."""
import argparse
import hashlib
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from persistence_disk import open_image
from test_vm import verified_asset, command, output_lines, boot_passed

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true', help='Exclusively create new private 32 MiB image; never overwrite')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--phase', choices=['save', 'load'])
    args = parser.parse_args()
    if args.run and not args.phase:
        parser.error('--run requires --phase')
    if args.create and args.run:
        parser.error('--create and --run are separate operations')
    fd = open_image(ROOT, create=args.create)
    try:
        if args.create:
            print('Created private blank build/guest-state/state.raw; no VM started')
            return 0
        assets = json.loads((ROOT / 'boot/boot-assets.lock.json').read_text())
        qemu, kernel = (verified_asset(assets[key]) for key in ['qemu', 'kernel'])
        manifest = json.loads((ROOT / 'build/boot/build-manifest.json').read_text())
        archive = ROOT / 'build/boot/roko-initramfs.cpio.gz'
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['initramfs_sha256']:
            raise ValueError('Initramfs mismatch')
        if not manifest.get('persistence_included'):
            raise ValueError('Rebuild userland with persistence helpers first')
        if not args.run:
            print('Persistence preflight passed; no VM started')
            return 0
        subprocess.run([sys.executable, str(ROOT / 'boot/verify-tooling.py')], check=True, timeout=60)
        cmd = command(qemu, kernel, archive)
        cmd[cmd.index('-m') + 1] = '512'
        # Inherited descriptor pins the checked inode, eliminating pathname swaps.
        cmd += ['-blockdev', json.dumps({'driver':'file','filename':f'/proc/self/fd/{fd}','node-name':'statefile'}),
                '-blockdev', json.dumps({'driver':'raw','file':'statefile','node-name':'state'}),
                '-device', 'virtio-blk-pci,drive=state,serial=roko-private-state']
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, pass_fds=(fd,))
        chunks, sent = [], False
        deadline = time.monotonic() + 90
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([proc.stdout], [], [], 1)
                if ready:
                    chunk = os.read(proc.stdout.fileno(), 65536)
                    if chunk:
                        chunks.append(chunk)
                    elif proc.poll() is not None:
                        break
                log = b''.join(chunks).decode(errors='replace')
                if not sent and 'ROKO_BUSYBOX_PRESENT' in log:
                    shell = ('set -e; /bin/busybox insmod /opt/roko/virtio_blk.ko; '
                             'export PYTHONHOME=/opt/roko/python; export PATH=/bin; '
                             '/opt/roko/python/bin/python3.12 /opt/roko/persistence-check.py ' + args.phase +
                             '; /bin/busybox sync; /bin/busybox poweroff -f\n')
                    proc.stdin.write(shell.encode()); proc.stdin.flush(); sent = True
                if proc.poll() is not None:
                    break
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                tail = proc.communicate(timeout=5)[0]
            except subprocess.TimeoutExpired:
                proc.kill(); tail = proc.communicate()[0]
        log = (b''.join(chunks) + tail).decode(errors='replace')
        lines = output_lines(log)
        marker = 'ROKO_PERSISTENCE_' + args.phase.upper() + '_PASSED sequence=1'
        passed = boot_passed(log, manifest['build_id']) and marker in lines and 'Power down' in log and proc.returncode == 0
        if args.phase == 'load':
            passed &= 'ROKO_PERSISTENCE_RECOVERY_PASSED' in lines
        report = {'phase':args.phase,'passed':bool(passed),'qemu_returncode':proc.returncode,
                  'network_enabled':False,'host_disks_attached':False,'private_guest_disk_attached':True,
                  'initramfs_sha256':manifest['initramfs_sha256'],
                  'scope':'Explicit bounded checkpoint journal; not a mounted filesystem or automatic persistence'}
        (ROOT / f'results/persistence-{args.phase}-serial.txt').write_text(log)
        (ROOT / f'results/persistence-{args.phase}.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        return 0 if passed else 1
    finally:
        os.close(fd)

if __name__ == '__main__':
    raise SystemExit(main())
