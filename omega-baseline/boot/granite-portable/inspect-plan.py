#!/usr/bin/env python3
"""Read/hash small binaries and manifests only; no compilation or native/model execution."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/granite-portable-preparation'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def elf(path,flag):return subprocess.run(['readelf',flag,str(path)],capture_output=True,text=True,check=True,timeout=10).stdout

def main():
    host=json.loads((ROOT/'granite-runtime.lock.json').read_text())
    actual_root=json.loads((ROOT/'build/disk-root-guest/root-source.json').read_text())
    base=ROOT/'build-src/basilisk-stage'
    records={r['path']:r for r in json.loads((base/'debian-files.lock.json').read_text())['files']}
    package_stage=ROOT/'build-src/cosmic-files-portals-stage'
    package=next(p for p in json.loads((package_stage/'debian-packages.lock.json').read_text())['packages'] if p['package']=='libgomp1')
    archive=package_stage/'apt/archives'/Path(package['filename']).name
    if sha(archive)!=package['sha256']:raise ValueError('Pinned package changed')
    package_files={r['path']:r for r in json.loads((package_stage/'debian-files.lock.json').read_text())['files']}
    specs={
        'libllama.so.0':'build/llama/bin/libllama.so.0.9.0',
        'libggml.so.0':'build/llama/bin/libggml.so.0.29.0',
        'libggml-base.so.0':'build/llama/bin/libggml-base.so.0.29.0',
        'libggml-cpu.so.0':'build/llama/bin/libggml-cpu.so.0.29.0'}
    private={}
    for soname,relative in specs.items():
        path=ROOT/relative
        if sha(path)!=host['files'][relative]:raise ValueError('Host library changed')
        private[soname]=path
    gomp_relative='usr/lib/x86_64-linux-gnu/libgomp.so.1.0.0'
    gomp=package_stage/'sysroot'/gomp_relative
    if sha(gomp)!=package_files[gomp_relative]['sha256']:raise ValueError('Official libgomp changed')
    private['libgomp.so.1']=gomp
    systems={}
    for soname in ('libstdc++.so.6','libgcc_s.so.1','libc.so.6','libm.so.6','ld-linux-x86-64.so.2'):
        path=(base/'sysroot/usr/lib/x86_64-linux-gnu'/soname).resolve()
        relative=str(path.relative_to((base/'sysroot').resolve()))
        digest=sha(path)
        if records[relative]['sha256']!=digest or actual_root['entries']['usr/lib/x86_64-linux-gnu/'+soname]['sha256']!=digest:
            raise ValueError('Guest system library differs from accepted disk root')
        systems[soname]=path
    admission=json.loads((ROOT/'results/granite-host-avx2/binary-admission.json').read_text())
    helper=ROOT/admission['binary']
    if sha(helper)!=admission['binary_sha256']:raise ValueError('Measured helper changed')
    all_libs={**private,**systems}
    available={}
    for name,path in all_libs.items():
        info=elf(path,'-V')
        section=info.split('Version definition section',1)[1].split('Version needs section',1)[0] if 'Version definition section' in info else ''
        available[name]=set(re.findall(r'Name: (\S+)',section))
    checks=[]
    for name,path in {'infer':helper,**private,**systems}.items():
        dynamic=elf(path,'-d');needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
        if not set(needed)<=set(all_libs):raise ValueError('Unresolved dependency '+name+repr(needed))
        info=elf(path,'-V');current=None;requirements={}
        for line in info.split('Version needs section',1)[-1].splitlines() if 'Version needs section' in info else []:
            match=re.search(r'File: (\S+)',line)
            if match:current=match[1];requirements[current]=[]
            match=re.search(r'Name: (\S+)',line)
            if match and current:
                if match[1] not in available[current]:raise ValueError('Guest ABI missing '+current+':'+match[1])
                requirements[current].append(match[1])
        checks.append({'name':name,'source':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size,'needed':needed,'required_versions':requirements,'runpath':re.findall(r'\(RUNPATH\).*?\[(.*?)\]',dynamic)})
    native_bytes=sum(p.stat().st_size for p in private.values())+helper.stat().st_size+(ROOT/'build/granite-guest-helper/omega-granite-guest').stat().st_size
    free=shutil.disk_usage(ROOT).free;image=4608*1024**2;reserve=4*1024**3
    manifest=json.loads((ROOT/'build-src/granite-portable-stage/source-v2/manifest.json').read_text())
    report={'status':'static-source-and-ELF-plan-only','user_target':{'ram_gb':32,'graphics':'Intel integrated graphics, exact capability unverified','cpu':'unknown; optional AVX2 proof plus generic fallback'},'cpu_probe_compiled':False,'native_runtime_executed':False,'model_loaded':False,'guest_booted':False,'native_source_bytes_reusable':native_bytes,'source_stage_bytes':manifest['source_bytes'],'libgomp_official_package':package,'libgomp_already_in_accepted_root':gomp_relative in actual_root['entries'],'ELF_version_requirements_satisfied_by_pinned_guest_closure':True,'elf_closure':checks,'runtime_resolution_admission':'Pending explicit loader --list/startup in a relocated closure; absolute old RUNPATH metadata remains in unchanged libraries','model_disk':{'existing_weights_bytes':4230976352,'planned_logical_image_bytes':image,'model_readonly':True,'weights_in_initramfs':False,'free_disk_bytes_now':free,'required_reserve_bytes':reserve,'conservative_fully_allocated_admission_bytes':image+reserve,'conservative_shortfall_bytes':max(0,image+reserve-free),'minimum_weights_plus_reserve_shortfall_bytes':max(0,4230976352+reserve-free),'disk_creation_admitted_now':free>=image+reserve},'memory':{'host_measured_native_peak_kib':4260376,'disk_root_idle_memtotal_kib':4016228,'disk_root_idle_memavailable_kib':3273152,'possible_test_guest_ram_gib':6,'test_is_environment_limit_not_target_hardware_limit':True,'combined_fit':'Not measured; retain host 2 GiB available reserve and serial-only gate before desktop'},'next_gate':['Finish active corner VM and obtain explicit lane grant.','Compile only baseline CPU probe; exercise full/absent/OS-state feature decisions.','Stage exact helper/libraries plus official libgomp; use pinned guest loader, inspect complete relocated resolution and startup.','Only after separate disk budget admission, create/hash a new read-only model image; keep accepted root and state disks unchanged.','Serial-only bounded TCG test first, then actual avatar composer/CLI/check/cancel test; preserve 120s UI cap and report timeouts.']}
    (OUT/'runtime-plan.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','native_source_bytes_reusable','source_stage_bytes','ELF_version_requirements_satisfied_by_pinned_guest_closure','model_disk')},indent=2))

if __name__=='__main__':main()
