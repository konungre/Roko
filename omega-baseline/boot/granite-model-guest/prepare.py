#!/usr/bin/env python3
"""Prepare a ~15 MB candidate runtime; no model reading, assembly or VM."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'build-src/granite-raw-block-stage/source-v1'
OUT = ROOT / 'build-src/granite-model-guest-stage/candidate-v2'
GUEST_ROOT = '/run/granite-model-probe/roko'
RECEIPT = ROOT / 'results/granite-raw-synthetic/attempt-1/validation.json'
RECEIPT_SHA = 'f6ad40e000a4279acf4e82406f59a039bb3fe02c56d833bbc1b361e3923c74e5'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def synthetic_proof():
    data = RECEIPT.read_bytes()
    if sha(data) != RECEIPT_SHA:
        raise ValueError('Synthetic receipt changed')
    proof = json.loads(data)
    if (proof['passed'] is not True or proof['model_attached'] is not False
            or proof['fixture_unchanged'] is not True or proof['root_unchanged'] is not True
            or proof['guest']['checks']['zero_tail_bytes'] != 160 or proof['guest']['checks']['mmap_checked'] is not True):
        raise ValueError('Synthetic block gate did not pass')
    return proof


def supervisor_variant(original):
    text = original.replace('import argparse\n', 'import argparse\nimport resource\nfrom memory_guard import limits, observe, reason as memory_reason\n', 1)
    before = '    started = time.monotonic()\n    try:\n        native = subprocess.Popen(command, close_fds=True, start_new_session=False)'
    after = '''    started = time.monotonic()
    peak_tree_rss = 0
    minimum_available = None
    try:
        limits()
        native = subprocess.Popen(command, close_fds=True, start_new_session=False)'''
    if text.count(before) != 1:
        raise ValueError('Supervisor native-start anchor changed')
    text = text.replace(before, after)
    before = '            descendants(os.getpid(), known)\n            if interrupted or not parent_alive():'
    after = '''            rows = descendants(os.getpid(), known)
            observed = observe(rows)
            peak_tree_rss = max(peak_tree_rss, observed['aggregate_rss_bytes'])
            minimum_available = observed['guest_available_bytes'] if minimum_available is None else min(minimum_available, observed['guest_available_bytes'])
            exceeded = memory_reason(observed)
            if exceeded:
                reason = exceeded
                code = 137
                break
            if interrupted or not parent_alive():'''
    if text.count(before) != 1:
        raise ValueError('Supervisor monitor anchor changed')
    text = text.replace(before, after)
    before = '        print(f\'ROKO_SUPERVISOR reason={reason} descendants_cleaned=1\', file=sys.stderr, flush=True)'
    after = '''        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        print(f'ROKO_SUPERVISOR_USAGE max_rss_kib={usage.ru_maxrss} minor_faults={usage.ru_minflt} major_faults={usage.ru_majflt} peak_tree_rss_bytes={peak_tree_rss} minimum_guest_available_bytes={minimum_available}', file=sys.stderr, flush=True)
''' + before
    if text.count(before) != 1:
        raise ValueError('Supervisor completion anchor changed')
    text = text.replace(before, after)
    old_sleep = '            time.sleep(.02)\n    finally:'
    if text.count(old_sleep) != 1:
        raise ValueError('Supervisor poll anchor changed')
    return text.replace(old_sleep, '            time.sleep(.1)\n    finally:')


def stage():
    synthetic_proof()
    manifest = json.loads((BASE / 'manifest.json').read_text())
    files = {}
    modes = {}
    for name, expected in manifest['files'].items():
        if not name.startswith('opt/roko/'):
            raise ValueError('Unexpected source closure prefix')
        data = (BASE / name).read_bytes()
        if sha(data) != expected['sha256'] or len(data) != expected['bytes']:
            raise ValueError('Raw source stage changed')
        dest = name.removeprefix('opt/roko/')
        files[dest] = data
        modes[dest] = 0o444
    runtime = json.loads(files.pop('granite-portable-runtime.lock.json'))
    raw = json.loads(files['granite-raw-transport.lock.json'])
    raw.update(status='synthetic-proven-awaiting-model-execution-grant', reviewed_admission=False,
               synthetic_receipt_sha256=RECEIPT_SHA)
    files['granite-raw-transport.lock.json'] = (json.dumps(raw, indent=2) + '\n').encode()
    original = files['runtime/granite/supervise.py'].decode()
    guarded = supervisor_variant(original)
    files['runtime/granite/supervise.py'] = guarded.encode()
    files['runtime/granite/memory_guard.py'] = (HERE / 'memory_guard.py').read_bytes()
    modes['runtime/granite/memory_guard.py'] = 0o444
    selector = files['adapters/runtime_select.py'].decode()
    selector = selector.replace("manifest.get('status') != 'guest-runtime-admitted'", "manifest.get('status') != 'candidate-runtime-admitted-for-single-probe'")
    files['adapters/runtime_select.py'] = selector.encode()
    provider = files['adapters/granite_guest.py'].decode()
    before = '''        except Exception as error:
            return providers.LLMResponse().with_error(str(error))'''
    after = '''        except Exception as error:
            # Preserve bounded native diagnostics even if the Python deadline fires.
            if 'output' in locals():
                self.last.update(raw_output=bytes(output['stdout']).decode('utf-8', errors='replace'),
                                 stderr=bytes(output['stderr']).decode('utf-8', errors='replace'),
                                 elapsed_seconds=round(time.monotonic() - started, 3),
                                 executed_actions=0)
                if 'proc' in locals():
                    self.last['returncode'] = proc.returncode
            return providers.LLMResponse().with_error(str(error))'''
    if provider.count(before) != 1:
        raise ValueError('Provider failure-preservation anchor changed')
    files['adapters/granite_guest.py'] = provider.replace(before, after).encode()
    relocation = json.loads((ROOT / 'results/granite-portable-preparation/relocation-admission.json').read_text())
    native_root = ROOT / 'build/granite-portable-runtime-v1'
    system = {}
    root_entries = json.loads((ROOT / 'build/disk-root-guest/root-source.json').read_text())['entries']
    for name, expected in relocation['files'].items():
        data = (native_root / name).read_bytes()
        if sha(data) != expected['sha256'] or len(data) != expected['bytes']:
            raise ValueError('Admitted native closure changed')
        relative = name.removeprefix('relocated-v2/')
        if relative.startswith('system/'):
            guest_path = 'usr/lib/x86_64-linux-gnu/' + Path(relative).name
            if root_entries[guest_path]['sha256'] != expected['sha256']:
                raise ValueError('Native system dependency differs from accepted root')
            system['/' + guest_path] = expected['sha256']
        else:
            destination = 'runtime/granite/' + relative
            files[destination] = data
            modes[destination] = 0o555
    library_names = ('libllama.so.0','libggml.so.0','libggml-base.so.0','libggml-cpu.so.0','libgomp.so.1')
    resolution = {n:GUEST_ROOT+'/runtime/granite/avx2/lib/'+n for n in library_names}
    resolution.update({Path(p).name:p for p in system})
    runtime.update(status='candidate-only-awaiting-execution-grant', optimized_loader_admitted=False,
                   admission_scope='Single bounded probe candidate; no prior real-model guest success asserted',
                   files={name:sha(data) for name,data in files.items()}, system_files=system,
                   optimized_resolution=resolution)
    files['granite-portable-runtime.lock.json'] = (json.dumps(runtime,indent=2)+'\n').encode()
    modes['granite-portable-runtime.lock.json'] = 0o444
    total = sum(map(len, files.values()))
    if total > 20 * 1024**2:
        raise ValueError('Candidate closure exceeds 20 MiB')
    OUT.mkdir(parents=True, exist_ok=False)
    for name,data in files.items():
        target = OUT / 'roko' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(modes[name])
    report = {'status':'candidate-staged-not-execution-admitted','payload_bytes':total,
              'model_included':False,'model_read':False,'guest_booted':False,
              'base_stage_manifest_sha256':sha((BASE/'manifest.json').read_bytes()),
              'synthetic_receipt_sha256':RECEIPT_SHA,
              'files':{name:{'sha256':sha(data),'bytes':len(data),'mode':modes[name]} for name,data in files.items()},
              'native_runtime_bytes_unchanged':True, 'guest_system_files':system,
              'memory_guards':'Sampled aggregate native RSS <=5 GiB; guest MemAvailable >=512 MiB; per-process RLIMIT_AS 6 GiB',
              'prior_wrong_literal_and_qwen_results_preserved':True}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'supervisor.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),guarded.splitlines(True),fromfile='cancellation-tested-supervisor',tofile='memory-guarded-variant')))
    return report


if __name__ == '__main__':
    result=stage()
    (ROOT/'results/granite-model-guest-preparation/stage.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','guest_system_files')},indent=2))
