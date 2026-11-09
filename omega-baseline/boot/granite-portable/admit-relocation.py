#!/usr/bin/env python3
"""Short no-model relocation gate using exact pinned runtime and guest libraries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/granite-portable-runtime-v1'
RESULTS=ROOT/'results/granite-portable-preparation'
spec=importlib.util.spec_from_file_location('selector',Path(__file__).with_name('runtime_select.py'))
selector=importlib.util.module_from_spec(spec);spec.loader.exec_module(selector)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if (RESULTS/'relocation-admission.json').exists():raise ValueError('No overwrite of admission')
    plan=json.loads((RESULTS/'runtime-plan.json').read_text())
    closure=OUT/'relocated-v2';closure.mkdir(mode=0o700)
    rows={r['name']:r for r in plan['elf_closure']}
    files={}
    def copy(source,dest,expected):
        if sha(source)!=expected:raise ValueError('Source binary changed')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes());dest.chmod(0o555)
        files[str(dest.relative_to(OUT))]={'sha256':sha(dest),'bytes':dest.stat().st_size}
    private=closure/'avx2/lib';system=closure/'system'
    for name in selector.LIBRARIES:
        row=rows[name];copy(ROOT/row['source'],private/name,row['sha256'])
    for name in ('libc.so.6','libm.so.6','libgcc_s.so.1','libstdc++.so.6','ld-linux-x86-64.so.2'):
        row=rows[name];copy(ROOT/row['source'],system/name,row['sha256'])
    helper=closure/'avx2/infer';copy(ROOT/rows['infer']['source'],helper,rows['infer']['sha256'])
    generic=closure/'generic/infer';pin=json.loads((ROOT/'results/granite-guest-build/binary-admission.json').read_text())
    copy(ROOT/pin['binary'],generic,pin['binary_sha256'])
    cpuid=OUT/'cpuid-probe';probe=closure/'cpuid-probe';copy(cpuid,probe,sha(cpuid))
    loader=system/'ld-linux-x86-64.so.2'
    ignored=':'.join([str(helper),*selector.LIBRARIES,*(str(private/n) for n in selector.LIBRARIES)])
    common=[str(loader),'--inhibit-cache','--glibc-hwcaps-mask','','--inhibit-rpath',ignored,'--library-path',str(private)+':'+str(system)]
    env={'PATH':'/usr/bin:/bin','LC_ALL':'C','OMP_NUM_THREADS':'1'}
    def run(args):return subprocess.run(args,capture_output=True,text=True,timeout=5,cwd=closure,env=env)
    expected={n:str(private/n) for n in selector.LIBRARIES}
    expected.update({n:str(system/n) for n in ('libc.so.6','libm.so.6','libgcc_s.so.1','libstdc++.so.6','ld-linux-x86-64.so.2')})
    listing=run(common+['--list',str(helper)])
    if listing.returncode or listing.stderr:raise ValueError('Loader list failed: '+listing.stderr)
    actual=selector.resolved_paths(listing.stdout)
    if actual!=expected:raise ValueError('Unexpected resolution: '+repr(actual))
    (RESULTS/'relocated-loader-list.txt').write_text(listing.stdout)
    smoke=run(common+[str(helper)])
    if smoke.returncode!=2 or 'expected --model' not in smoke.stderr:raise ValueError('Optimized helper startup failed')
    generic_smoke=run(common+[str(generic)])
    if generic_smoke.returncode!=2 or 'expected --model' not in generic_smoke.stderr:raise ValueError('Generic helper startup failed')
    cpuid_run=run(common+[str(probe)])
    if cpuid_run.returncode:raise ValueError('Guest-library CPUID probe failed')
    proof=json.loads(cpuid_run.stdout)
    if selector.choose(proof,True)!='avx2':raise ValueError('Expected current host proof missing')
    # Removing one copy may expose original host RUNPATH; that is detected, never admitted.
    missing=private/'libggml-cpu.so.0';held=private/'held-libggml-cpu.so.0';missing.rename(held)
    try:
        negative=run(common+['--list',str(helper)])
        rejected=negative.returncode!=0 or selector.resolved_paths(negative.stdout)!=expected
        if not rejected:raise ValueError('Missing private dependency was not rejected')
    finally:held.rename(missing)
    for relative,pin in files.items():
        if sha(OUT/relative)!=pin['sha256']:raise ValueError('Final copied payload changed')
    source=ROOT/'boot/granite-portable/cpuid-probe.c'
    report={'status':'portable-closure-host-relocation-admitted-not-guest-or-model-tested',
            'files':files,'native_payload_and_diagnostic_system_bytes':sum(p['bytes'] for p in files.values()),
            'reused_native_sources_unchanged':True,'compiler_command':['/usr/bin/cc','-O2','-std=c11','-Wall','-Wextra','-Werror','-march=x86-64','-mtune=generic',str(source),'-o',str(cpuid)],
            'cpu_probe_source_sha256':sha(source),'cpu_probe_binary_sha256':sha(cpuid),
            'compiler_version':subprocess.run(['/usr/bin/cc','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0],
            'actual_cpuid_all_allowed_cpus':proof,'generic_fallback_source_tests_passed':True,
            'loader_command':common,'resolved_libraries':actual,'original_host_library_resolution_allowed':False,
            'missing_private_library_negative_gate_rejected':rejected,'optimized_start_returncode':smoke.returncode,'generic_start_returncode':generic_smoke.returncode,
            'runtime_runpaths_retained_but_unused':True,'guest_booted':False,'model_loaded':False,'model_disk_created':False,'default_model_changed':False,
            'source_only_provider_still_fail_closed':True,
            'limitation':'CPU dispatch exercised on this host; simulated negative proofs tested. No non-AVX2 physical CPU or TCG feature probe has run.'}
    (RESULTS/'relocation-admission.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','native_payload_and_diagnostic_system_bytes','actual_cpuid_all_allowed_cpus','missing_private_library_negative_gate_rejected','guest_booted','model_loaded')},indent=2))


if __name__=='__main__':main()
