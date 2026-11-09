#!/usr/bin/env python3
"""Small source-only derivative; no native compile, disk, model loading or VM."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build-src/granite-portable-stage/source-v2'
spec=importlib.util.spec_from_file_location('base_guest_prepare',ROOT/'boot/granite-guest/prepare.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def source_variant():
    original=(ROOT/'boot/granite-guest/granite_guest.py').read_text()
    text=original.replace('import providers\n','import providers\nfrom runtime_select import start_runtime, supervised_prefix, stop_supervisor\n',1)
    start=text.index('    def start(self):',text.index('class GraniteGuestProvider'))
    end=text.index('    def stop(self):',start)
    text=text[:start]+'''    def start(self):
        start_runtime(self, verified_file)

'''+text[end:]
    before="args = [str(self.executable), '--model', str(self.model),"
    after="args = [*supervised_prefix(self.root, self.command_prefix), '--model', str(self.model),"
    if text.count(before)!=1:raise ValueError('Native command anchor changed')
    text=text.replace(before,after)
    before='''                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=5)'''
    if text.count(before)!=1:raise ValueError('Native cleanup anchor changed')
    text=text.replace(before,'                    stop_supervisor(proc)')
    return original,text


def stage():
    files,old=base.sources();original,variant=source_variant()
    files['opt/roko/adapters/granite_guest.py']=variant.encode()
    files['opt/roko/adapters/runtime_select.py']=(HERE/'runtime_select.py').read_bytes()
    files['opt/roko/runtime/granite/supervise.py']=(HERE/'supervise.py').read_bytes()
    # The genuine controller/store/event source closure is included, not a mock CLI.
    for name in ('working_state.py','state_store.py','avatar_events.py'):
        files['opt/roko/adapters/'+name]=(ROOT/'adapters'/name).read_bytes()
    files.pop('opt/roko/granite-guest-runtime.lock.json')
    runtime={'status':'source-only-not-built','optimized_loader_admitted':False,
             'files':{k.removeprefix('opt/roko/'):hashlib.sha256(v).hexdigest() for k,v in files.items()},
             'system_files':{},'optimized_resolution':{},
             'limits':'No admission until CPUID probe, explicit loader closure and cancellation have passed'}
    files['opt/roko/granite-portable-runtime.lock.json']=(json.dumps(runtime,indent=2)+'\n').encode()
    OUT.mkdir(parents=True,exist_ok=False)
    for name,data in files.items():
        path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(0o444)
    manifest={'status':'source-only-not-built','model_included':False,'native_binaries_included':False,
              'cpuid_probe_compiled':False,'model_loaded':False,'guest_booted':False,
              'target_hardware':'User stated 32 GB RAM and Intel integrated graphics; exact CPU unknown. No GPU inference claim.',
              'current_test_memory_is_not_user_hardware_limit':True,
              'omega_commit':old['omega_commit'],'source_bytes':sum(map(len,files.values())),
              'files':{k:{'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v)} for k,v in files.items()},
              'measured_provider_unchanged_sha256':hashlib.sha256(original.encode()).hexdigest(),
              'variant_sha256':hashlib.sha256(variant.encode()).hexdigest(),
              'cpu_probe_source_sha256':hashlib.sha256((HERE/'cpuid-probe.c').read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'provider.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),variant.splitlines(True),fromfile='measured-provider-unchanged',tofile='portable-supervised-variant')))
    return manifest


if __name__=='__main__':
    report=stage();print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
