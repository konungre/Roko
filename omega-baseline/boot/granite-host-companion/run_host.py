#!/usr/bin/env python3
"""Explicit reviewed native-host gate; no VM, model copy, service or UI claim."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import prepare

ROOT=prepare.ROOT
HERE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');parser.add_argument('--cancel-only',action='store_true');args=parser.parse_args()
    plan={'scope':'Exact-Python-3.13 native host current portable provider plus actual avatar subprocess bridge',
          'requests':['Exact matched Omega 7*8 request','Actual bridge/CLI 7*8 request, different CLI template','Actual native-child cancellation'],
          'negative_fixture':'Actual CLI propose 55 for 7*8, deterministic rejection, not model output',
          'native_seconds':60,'provider_seconds':70,'startup_seconds':30,'outer_seconds':300,
          'native_rss_cap_bytes':5*1024**3,'outer_rss_cap_bytes':int(5.5*1024**3),
          'host_available_floor_bytes':2*1024**3,'disk_floor_bytes':4*1024**3,
          'guest_inference':False,'guest_host_service':False,'graphical_avatar_tested':False}
    if args.cancel_only:plan['requests']=['Actual mapped native/model-child cancellation only; no repeated arithmetic runs']
    if not args.run:
        print(json.dumps(plan,indent=2));return 0
    free=shutil.disk_usage(ROOT).free
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
    if free<4*1024**3+16*1024**2 or available<7*1024**3:raise ValueError('Host companion disk/memory admission failed')
    build=ROOT/'build/granite-host-companion';results=ROOT/'results/granite-host-companion'
    build.mkdir(mode=0o700,exist_ok=True);results.mkdir(mode=0o700,exist_ok=True)
    attempt=1
    while (build/f'attempt-{attempt}').exists() or (results/f'attempt-{attempt}').exists():attempt+=1
    active=build/f'attempt-{attempt}';result=results/f'attempt-{attempt}'
    active.mkdir(mode=0o700);result.mkdir(mode=0o700)
    expected=json.loads((prepare.OUT.parent/'manifest.json').read_text())
    for name,pin in expected['source_files'].items():
        path=prepare.OUT/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pin['sha256']:raise ValueError('Host source candidate changed')
    shutil.copytree(prepare.OUT,active/'roko')
    root=active/'roko';manifest=root/'host-companion.lock.json'
    lock=json.loads(manifest.read_text());lock.update(status='host-companion-admitted-for-probe',optimized_loader_admitted=True)
    manifest.chmod(0o644);manifest.write_text(json.dumps(lock,indent=2)+'\n');manifest.chmod(0o444)
    spec=importlib.util.spec_from_file_location('exact_host_model_admission',root/'adapters/host_model.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    fd=None;report=dict(plan,passed=False,model_before=None,source_candidate_unchanged=True,errors=[],free_disk_before=free)
    try:
        start=time.monotonic();fd,report['model_before']=model.open_model(seconds=120)
        report['model_hash_before_seconds']=round(time.monotonic()-start,3)
        command=[sys.executable,str(ROOT/'boot/granite-guest/run-bounded.py'),'--out',str(result/'monitor'),
                 '--seconds','300','--start-available-kib',str(7*1024**2),'--reserve-kib',str(2*1024**2),
                 '--max-rss-kib',str(int(5.5*1024**2)),'--minimum-free-bytes',str(4*1024**3),
                 '--disk-path',str(ROOT),'--',sys.executable,str(ROOT/'scripts/no-network.py'),
                 str(root/'runtime/python313'),str(HERE/'profile.py'),'--root',str(root),
                 '--out',str(result/'profile'),'--run-model']
        if args.cancel_only:command.append('--cancel-only')
        report['command']=command
        # The existing bounded monitor owns timeout/process-tree termination.
        with (result/'runner-output.txt').open('xb') as stream:
            completed=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=False)
        report['monitor_returncode']=completed.returncode
        for name,path in [('monitor',result/'monitor/monitor.json'),('profile',result/'profile/evaluation.json')]:
            if path.exists():report[name]=json.loads(path.read_text())
        if completed.returncode:report['errors'].append('Native-host gate reported failure; inspect original monitor/profile logs')
    except BaseException as error:
        report['errors'].append(type(error).__name__+': '+str(error))
    finally:
        if fd is not None:
            try:
                start=time.monotonic();report['model_after']=model.verify(fd,report['model_before'],seconds=120)
                report['model_hash_after_seconds']=round(time.monotonic()-start,3)
                report['model_unchanged']=report['model_after']==report['model_before']
            except BaseException as error:report['errors'].append('Model postcheck: '+str(error))
            os.close(fd)
        report['free_disk_after']=shutil.disk_usage(ROOT).free
        report['passed']=not report['errors'] and report.get('profile',{}).get('passed') is True and report.get('model_unchanged') is True
        report['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
        report['candidate_manifest_sha256']=hashlib.sha256((prepare.OUT.parent/'manifest.json').read_bytes()).hexdigest()
        report['result_path']=str(result.relative_to(ROOT))
        (result/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','errors','result_path','free_disk_after']},indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
