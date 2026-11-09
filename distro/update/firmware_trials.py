#!/usr/bin/env python3
"""Actual OVMF/systemd-boot counting on a private disposable GPT/FAT disk.

No host block device, ISO, NIC, physical firmware or production update is touched.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_probe import verify_runtime
from probe_gate import serial_evidence


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def gpt(path):
    sectors=524288;first=2048;last=sectors-2049
    entries=bytearray(128*128)
    entries[:16]=uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
    entries[16:32]=uuid.UUID('726f6b6f-0000-4000-8000-000000000001').bytes_le
    struct.pack_into('<QQQ',entries,32,first,last,0)
    name='ROKO_TEST_ESP'.encode('utf-16le');entries[56:56+len(name)]=name
    def header(current,backup,table):
        h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIIIQQQQ',h,8,0x10000,92,0,0,current,backup,34,sectors-34)
        h[56:72]=uuid.UUID('726f6b6f-0000-4000-8000-000000000002').bytes_le
        struct.pack_into('<QIII',h,72,table,128,128,binascii.crc32(entries)&0xffffffff)
        struct.pack_into('<I',h,16,binascii.crc32(h[:92])&0xffffffff);return h
    with path.open('xb') as f:
        f.truncate(sectors*512)
        mbr=bytearray(512);mbr[446+4]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
        f.write(mbr);f.write(header(1,sectors-1,2));f.write(entries)
        f.seek((sectors-33)*512);f.write(entries);f.write(header(sectors-1,1,sectors-33))
        f.flush();os.fsync(f.fileno())
    path.chmod(0o600)
    return first,(last-first+1)//2


def run(tools,runtime,lock,good,bad,output):
    tools,runtime,lock,good,bad,output=map(Path,(tools,runtime,lock,good,bad,output))
    verify_runtime(runtime,lock)
    output.mkdir(mode=0o700)
    ovmf=tools/'usr/share/OVMF';firmware=ovmf/'OVMF_CODE_4M.fd'
    variables=output/'vars.fd';shutil.copyfile(ovmf/'OVMF_VARS_4M.fd',variables);variables.chmod(0o600)
    esp=output/'esp.img';offset,blocks=gpt(esp)
    env={'PATH':'/usr/bin:/bin','LC_ALL':'C','MTOOLS_SKIP_CHECK':'1','LD_LIBRARY_PATH':str(tools/'usr/lib/x86_64-linux-gnu')}
    subprocess.run([str(tools/'usr/sbin/mkfs.fat'),'-F','32','--offset',str(offset),str(esp),str(blocks)],env=env,check=True,capture_output=True)
    image=str(esp)+'@@'+str(offset*512)
    def mtool(name,*args):
        return subprocess.check_output([str(tools/'usr/bin'/name),'-i',image,*map(str,args)],env=env,stderr=subprocess.STDOUT)
    for directory in ('EFI','EFI/BOOT','loader','loader/entries'):mtool('mmd','::/'+directory)
    kernel=next((runtime/'boot').glob('vmlinuz-*'))
    sources={'EFI/BOOT/BOOTX64.EFI':tools/'usr/lib/systemd/boot/efi/systemd-bootx64.efi',
             'vmlinuz':kernel,'good.cpio.gz':good/'initramfs.cpio.gz','trial.cpio.gz':bad/'initramfs.cpio.gz'}
    for dest,source in sources.items():mtool('mcopy',source,'::/'+dest)
    entries={'loader.conf':'timeout 0\neditor no\nauto-entries no\nauto-firmware no\n',
             'roko-1.conf':'title Roko good\nversion 1\nsort-key roko\nlinux /vmlinuz\ninitrd /good.cpio.gz\noptions console=ttyS0 rdinit=/init panic=1\n',
             'roko-2+3.conf':'title Roko trial\nversion 2\nsort-key roko\nlinux /vmlinuz\ninitrd /trial.cpio.gz\noptions console=ttyS0 rdinit=/init panic=1\n'}
    for name,text in entries.items():
        p=output/name;p.write_text(text);mtool('mcopy',p,'::/loader/'+('' if name=='loader.conf' else 'entries/')+name)
    rows=[];library=runtime/'usr/lib/x86_64-linux-gnu';before_firmware=sha(firmware)
    admitted={'firmware_sha256':before_firmware,'bootloader_sha256':sha(sources['EFI/BOOT/BOOTX64.EFI']),
              'runtime_lock_sha256':sha(lock),'esp_before_sha256':sha(esp),'vars_before_sha256':sha(variables),
              'good_initramfs_sha256':sha(good/'initramfs.cpio.gz'),'trial_initramfs_sha256':sha(bad/'initramfs.cpio.gz')}
    (output/'admission.json').write_text(json.dumps(admitted,indent=2)+'\n')
    for attempt in range(1,5):
        command=[str(library/'ld-linux-x86-64.so.2'),'--inhibit-cache','--library-path',str(library),
                 str(runtime/'usr/bin/qemu-system-x86_64'),'-L',str(runtime/'usr/share/qemu'),
                 '-no-user-config','-nodefaults','-machine','q35,accel=tcg','-m','512','-smp','1',
                 '-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot',
                 '-drive','if=pflash,format=raw,unit=0,readonly=on,file='+str(firmware),
                 '-drive','if=pflash,format=raw,unit=1,file='+str(variables),
                 '-drive','if=none,id=esp,format=raw,file='+str(esp),'-device','virtio-blk-pci,drive=esp']
        started=time.monotonic()
        with (output/f'boot-{attempt}.serial').open('xb') as serial:
            proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=serial,stderr=subprocess.STDOUT,env={**env,'QEMU_MODULE_DIR':str(library/'qemu')})
            try:proc.wait(timeout=90)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait();raise RuntimeError('Firmware boot timed out; evidence retained')
        log=(output/f'boot-{attempt}.serial').read_text(errors='replace')
        listing=mtool('mdir','-b','::/loader/entries').decode();(output/f'entries-{attempt}.txt').write_text(listing)
        expected=f'roko-2+{3-attempt}-{attempt}.conf' if attempt<=3 else 'roko-2+0-3.conf'
        if attempt<=3:
            passed=proc.returncode==0 and log.count('ROKO_FOUNDATION_FAILED injected-trial-health')==1 and expected.lower() in listing.lower()
        else:
            manifest=json.loads((good/'manifest.json').read_text());passed=serial_evidence(log,manifest['build_id'],proc.returncode)['serial_contract_passed'] and expected.lower() in listing.lower()
        row={'attempt':attempt,'passed':passed,'returncode':proc.returncode,'seconds':time.monotonic()-started,
             'entries':listing,'serial_sha256':sha(output/f'boot-{attempt}.serial'),'child_reaped':True}
        rows.append(row);(output/f'boot-{attempt}.json').write_text(json.dumps(row,indent=2)+'\n')
        if not passed:raise RuntimeError('Unexpected firmware boot outcome')
    report={'schema':'roko-uefi-bootcount-v1','passed':all(r['passed'] for r in rows),'boots':rows,
            'firmware_unchanged':sha(firmware)==before_firmware,'admission':admitted,
            'esp_after_sha256':sha(esp),'vars_after_sha256':sha(variables),'network':False,
            'host_block_devices':False,'iso_used':False,'secure_boot_tested':False,
            'production_update_tested':False,'scope':'Actual virtual UEFI/systemd-boot fallback on disposable GPT/FAT disk'}
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('tools','runtime','lock','good','bad','output'):p.add_argument(n,type=Path)
    a=p.parse_args();r=run(a.tools,a.runtime,a.lock,a.good,a.bad,a.output);print(json.dumps({'passed':r['passed']}))
