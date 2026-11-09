#!/usr/bin/env python3
"""Separate timeout-only native rebuild and bounded guest candidate."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'boot/granite-model-guest'
sys.path.insert(0, str(OLD))
spec = importlib.util.spec_from_file_location('original_model_prepare', OLD / 'prepare.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
sha = original.sha
synthetic_proof = original.synthetic_proof
RECEIPT_SHA = original.RECEIPT_SHA
OUT = ROOT / 'build-src/granite-model-guest-stage/candidate-v3-900s'
BUILD = ROOT / 'build/granite-model-extended-helper'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one timeout anchor: ' + old)
    return text.replace(old, new)


def main():
    previous = ROOT / 'results/granite-model-guest/attempt-1/validation.json'
    previous_sha = sha(previous.read_bytes())
    if previous_sha != '31d60d5b2205dc7710d87eb41182f3aed09f5cbe6b9d7f4a26bd77a4b6b6ea55':
        raise ValueError('First failure receipt changed')
    source = ROOT / 'boot/granite-guest/granite-guest.cpp'
    before = source.read_text()
    if sha(source.read_bytes()) != '3bc9c00947fce0efc79631f5406ff00ff97e3a60dec85d60ff62f92e53317991':
        raise ValueError('Native source changed')
    after = replace_once(before, '    alarm(300);', '    alarm(900);')
    BUILD.mkdir(mode=0o700, exist_ok=False)
    target_source = BUILD / 'granite-guest-900.cpp'
    target_source.write_text(after)
    (BUILD / 'source.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original-300s',tofile='separate-900s')))
    common = ['/usr/bin/g++','-std=c++17','-march=x86-64','-mtune=generic','-I',str(ROOT/'build-src/llama.cpp/include'),'-I',str(ROOT/'build-src/llama.cpp/ggml/include'),str(target_source)]
    shared = ROOT/'build/llama/bin'
    static = ROOT/'build/granite-guest-helper/llama'
    commands = {
        'avx2': common[:1]+['-O2']+common[1:]+['-L',str(shared),'-Wl,-rpath,'+str(shared),'-lllama','-lggml','-lggml-base','-o',str(BUILD/'avx2-infer')],
        'generic': common[:1]+['-O3','-DNDEBUG']+common[1:]+[str(static/'src/libllama.a'),str(static/'ggml/src/libggml.a'),'-ldl',str(static/'ggml/src/libggml-cpu.a'),str(static/'ggml/src/libggml-base.a'),'-lm','-o',str(BUILD/'generic-infer')]
    }
    # Existing approved libraries only; no library or model rebuild.
    lib_pins = json.loads((ROOT/'granite-runtime.lock.json').read_text())['files']
    for path,pin in lib_pins.items():
        if path.startswith('build/llama/bin/') and sha((ROOT/path).read_bytes()) != pin:
            raise ValueError('Pinned shared library changed')
    static_pins = {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in static.rglob('*.a')}
    for name,cmd in commands.items():
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=20,check=True)
        (BUILD/(name+'-build.txt')).write_text(result.stdout+result.stderr)
    manifest=json.loads((original.OUT/'manifest.json').read_text())
    files={}
    modes={}
    for name,pin in manifest['files'].items():
        data=(original.OUT/'roko'/name).read_bytes()
        if sha(data)!=pin['sha256'] or len(data)!=pin['bytes']:
            raise ValueError('Original candidate changed')
        files[name]=data
        modes[name]=pin['mode']
    changes={
        'adapters/runtime_select.py':[("'--seconds', '300'", "'--seconds', '900'")],
        'adapters/granite_guest.py':[("started >= 310", "started >= 930"),("exceeded 310 seconds", "exceeded 930 seconds"),("max(.1, 310 -", "max(.1, 930 -")],
        'runtime/granite/supervise.py':[("args.seconds <= 300", "args.seconds <= 900")]
    }
    diffs={}
    for path,rows in changes.items():
        old=files[path].decode();new=old
        for left,right in rows:new=replace_once(new,left,right)
        files[path]=new.encode()
        diffs[path]=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/'+path,tofile='900s/'+path))
    # Observe existing native output, without additional native sampling or binary instrumentation.
    path='adapters/granite_guest.py';old=files[path].decode()
    new=replace_once(old,"            peak = 0\n", "            peak = 0\n            observed_phases = set()\n")
    anchor="                                output[key.data].extend(chunk)\n"
    insert=anchor+'''                                for phase, stream, marker in (
                                    ('model-tensors-log', 'stderr', b'load_tensors:'),
                                    ('context-log', 'stderr', b'llama_context:'),
                                    ('first-output-byte', 'stdout', None),
                                    ('native-completion-log', 'stderr', b'ROKO_GRANITE_LIMITS')):
                                    if phase not in observed_phases and key.data == stream and output[stream] and (marker is None or marker in output[stream]):
                                        observed_phases.add(phase)
                                        print('ROKO_GRANITE_GUEST_OBSERVATION ' + json.dumps({'phase': phase, 'request_elapsed_seconds': round(time.monotonic() - started, 3), 'meaning': 'existing output observed; not exact operation duration'}), flush=True)
'''
    new=replace_once(new,anchor,insert)
    files[path]=new.encode()
    diffs['output-observation.diff']=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='timeout-only-provider',tofile='output-observing-provider'))
    for name in ('generic','avx2'):
        files[f'runtime/granite/{name}/infer']=(BUILD/(name+'-infer')).read_bytes()
    runtime=json.loads(files['granite-portable-runtime.lock.json'])
    runtime['files']={name:sha(data) for name,data in files.items() if name!='granite-portable-runtime.lock.json'}
    files['granite-portable-runtime.lock.json']=(json.dumps(runtime,indent=2)+'\n').encode()
    OUT.mkdir(mode=0o700,exist_ok=False)
    for name,data in files.items():
        path=OUT/'roko'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(modes[name])
    report={'status':'prepared-timeout-only-awaiting-lane','original_failure_sha256':previous_sha,'native_source_before_sha256':sha(before.encode()),'native_source_after_sha256':sha(after.encode()),'native_source_delta':'alarm(300) -> alarm(900) only','commands':commands,'static_link_inputs':static_pins,'model_read':False,'payload_bytes':sum(map(len,files.values())),'files':{name:{'sha256':sha(data),'bytes':len(data),'mode':modes[name]} for name,data in files.items()},'bounds':{'native_seconds':900,'provider_seconds':930,'vm_seconds':1200,'startup_seconds':120},'source_diffs':diffs}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','source_diffs','commands','static_link_inputs')},indent=2))

if __name__=='__main__':main()
