#!/usr/bin/env python3
"""Run the exact existing two-fixture profile with only admitted host assets changed."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('matched_granite_profile', HERE / 'profile-host.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
sys.path.insert(0, str(ROOT / 'adapters'))
from working_state import WorkingState

ADMISSION = ROOT / 'results/granite-host-avx2/binary-admission.json'


class HostAvx2MeasurementProvider(baseline.HostMeasurementProvider):
    def start(self):
        # Preserve generic admission/model checks, then substitute only host helper.
        super().start()
        self.ready = False
        pin = json.loads(ADMISSION.read_text())
        if pin['status'] != 'host-only-avx2-binary-admitted' or pin['threads'] != 1:
            raise ValueError('Wrong host candidate admission')
        flags = [set(row.split(':', 1)[1].split()) for row in Path('/proc/cpuinfo').read_text().splitlines()
                 if row.startswith('flags')]
        if not flags or not all(set(pin['required_cpu_flags']) <= item for item in flags):
            raise ValueError('Unsupported host CPU')
        deadline = time.monotonic() + 30
        for name, expected in pin['pinned_runtime_files'].items():
            baseline.guest.verified_file(ROOT / name, expected, deadline)
        self.executable = ROOT / pin['binary']
        baseline.guest.verified_file(self.executable, pin['binary_sha256'], deadline)
        self.ready = True


def main():
    # Use the original request creation, messages, tools, grammar and chat unchanged.
    baseline.HostMeasurementProvider = HostAvx2MeasurementProvider
    baseline.main()
    out = Path(sys.argv[sys.argv.index('--out') + 1])
    path = out / 'evaluation.json'
    report = json.loads(path.read_text())
    pin = json.loads(ADMISSION.read_text())
    checks = []
    for row in report['cases']:
        stderr = (out / (row['id'] + '-native.txt')).read_text()
        for pattern, key in [(r'prompt_tokens=(\d+)', 'native_prompt_tokens'),
                             (r'generated_tokens=(\d+)', 'native_generated_tokens'),
                             (r'prompt eval time.*?([\d.]+) tokens per second', 'prompt_tokens_per_second'),
                             (r'(?m)^llama_perf_context_print:\s+eval time.*?([\d.]+) tokens per second', 'decode_tokens_per_second')]:
            match = re.search(pattern, stderr)
            if match:
                row[key] = float(match[1]) if 'second' in key else int(match[1])
        row['generation_cap_hit'] = row.get('native_generated_tokens') == 64
        row['runtime_repack_allocation_present'] = 'CPU_REPACK' in stderr
        state = WorkingState(row['id'], 'Independently check the actual measured model output')
        literal = row['id'] == 'literal-ready'
        state.add_evidence('source', 'synthetic-host-fixture', 'ready' if literal else 'Arithmetic: 7 * 8.')
        closed = False
        if row['format_valid']:
            call = row['calls'][0]
            state.propose(row['id'], call['name'], call['arguments'], ['source'])
            (state.verify_quote if literal else state.verify_arithmetic)()
            try:
                state.close()
                closed = True
            except ValueError:
                pass
        checks.append({'id': row['id'], 'closed': closed, 'state': state.snapshot()})
        if closed != row['exact_correct']:
            raise ValueError('Independent checker disagrees with exact comparison')
    report.update(
        runtime_variant='host-only AVX2 shared libraries, no repack, one thread',
        required_cpu_flags=pin['required_cpu_flags'], host_binary_sha256=pin['binary_sha256'],
        host_binary_admission_sha256=hashlib.sha256(ADMISSION.read_bytes()).hexdigest(),
        wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        default_model_changed=False,
        limitations='Two exact matched host fixtures only. AVX2 library configuration also differs in shared linkage, OpenMP/LLAMAFILE compilation, so do not attribute all change to one instruction. No TCG, portability, combined desktop integration or action authority. Model hashes warm page cache.')
    path.write_text(json.dumps(report, indent=2) + '\n')
    (out / 'controller-checks.json').write_text(json.dumps({
        'scope': 'Actual existing WorkingState checkers applied to recorded real native proposals; no extra model run',
        'working_state_sha256': hashlib.sha256((ROOT / 'adapters/working_state.py').read_bytes()).hexdigest(),
        'results': checks}, indent=2) + '\n')


if __name__ == '__main__':
    main()
