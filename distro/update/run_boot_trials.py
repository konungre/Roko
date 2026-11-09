#!/usr/bin/env python3
"""Boot fresh minimal probes under TCG to exercise the host-side trial journal.

No ISO, NIC, writable guest disk, firmware boot entry or production slot is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_probe import run
from boot_trial import Journal


def exercise(good, bad, runtime, lock, output):
    good,bad,runtime,lock,output=map(Path,(good,bad,runtime,lock,output))
    manifests=[json.loads((p/'manifest.json').read_text()) for p in (good,bad)]
    if manifests[0].get('injected_trial_failure') is not False or manifests[1].get('injected_trial_failure') is not True:
        raise ValueError('Require explicit good and injected-failure probe builds')
    output.mkdir(mode=0o700)
    journal_dir=output/'journal';journal_dir.mkdir(mode=0o700)
    journal=Journal(journal_dir)
    results=[]
    try:
        original={'slot':'A','sequence':1,'sha256':manifests[0]['initramfs_sha256']}
        candidate={'slot':'B','sequence':2,'sha256':manifests[1]['initramfs_sha256']}
        journal.initialize(original)
        journal.transition('arm',0,candidate=candidate)
        for attempt in range(1,5):
            choice=journal.transition('select',journal.read()['revision'])
            probe=bad if choice['selected']['slot']=='B' else good
            digest=hashlib.sha256((probe/'initramfs.cpio.gz').read_bytes()).hexdigest()
            if digest!=choice['selected']['sha256']:raise ValueError('Selected bytes changed')
            result=run(probe,runtime,lock,output/f'boot-{attempt}')
            serial=(output/f'boot-{attempt}'/'serial.txt').read_text()
            if attempt<=3:
                passed=(choice['selected']==candidate and not result['boot_passed'] and
                        result['returncode']==0 and result['child_reaped'] and
                        serial.count('ROKO_FOUNDATION_FAILED injected-trial-health')==1 and
                        'ROKO_FOUNDATION_NONROOT uid=1000' in serial and 'Power down' in serial)
            else:
                passed=choice['selected']==original and result['boot_passed'] and result['child_reaped']
            results.append({'attempt':attempt,'selection':choice,'vm':result,'expected_outcome_passed':passed})
            if not passed:raise RuntimeError('Unexpected trial/fallback boot outcome')
        # Independent healthy trial: confirmation follows measured guest success.
        healthy={'slot':'B','sequence':3,'sha256':manifests[0]['initramfs_sha256']}
        journal.transition('arm',journal.read()['revision'],candidate=healthy)
        choice=journal.transition('select',journal.read()['revision'])
        result=run(good,runtime,lock,output/'boot-healthy-trial')
        if not result['boot_passed'] or not result['child_reaped']:raise RuntimeError('Healthy trial failed')
        confirmed=journal.transition('confirm',choice['state']['revision'],nonce=choice['state']['active_nonce'])
        report={'schema':'roko-actual-minimal-boot-trials-v1','trials':results,
                'healthy_trial':result,'confirmed_state':confirmed['state'],
                'passed':confirmed['state']['good']==healthy,'actual_vm_boots':5,
                'network':False,'host_disks':False,'iso_used':False,
                'firmware_boot_selection_tested':False,'slot_installation_tested':False,
                'cosmic_tested':False,'model_inference_tested':False,
                'scope':'Actual minimal non-root guest boots selected by a host userspace journal; no production bootloader integration'}
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:
        journal.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('good','bad','runtime','lock','output'):parser.add_argument(name,type=Path)
    args=parser.parse_args()
    report=exercise(args.good,args.bad,args.runtime,args.lock,args.output)
    print(json.dumps({'passed':report['passed'],'actual_vm_boots':report['actual_vm_boots']}))
