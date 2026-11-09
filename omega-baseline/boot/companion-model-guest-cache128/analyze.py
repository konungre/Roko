"""Read completed attempt 3 and create non-overwriting evidence receipts. No VM."""
import hashlib
import json
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'results/companion-model-guest/attempt-3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value, raw=False):
    path = RESULT / name
    with path.open('x') as stream:
        stream.write(value if raw else json.dumps(value, indent=2) + '\n')
    path.chmod(0o444)
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def objects(text):
    result = []
    while text.strip():
        text = text.lstrip()
        value, end = json.JSONDecoder().raw_decode(text)
        result.append(value)
        text = text[end:]
    return result


def main():
    validation = json.loads((RESULT / 'validation.json').read_text())
    serial = (RESULT / 'serial.txt').read_text()
    assert validation['passed'] and validation['normal_exit']
    assert not validation['errors'] and not validation['guest_watchdog_fired']
    assert not validation['qemu_running_after_cleanup']
    assert validation['model_unchanged'] and validation['root_unchanged']
    assert sha(RESULT / 'serial.txt') == validation['serial.txt_sha256']
    records, observations, inspections, serial_parse_notes = [], [], [], []
    for line in serial.splitlines():
        for prefix, dest in [('ROKO_COMBINED_CLI_RESULT ', records),
                             ('ROKO_CORNER_OBSERVE_V2 ', observations),
                             ('ROKO_COMBINED_INSPECTION ', inspections)]:
            if line.startswith(prefix):
                try:
                    value, end = json.JSONDecoder().raw_decode(line[len(prefix):])
                    dest.append(value)
                    if line[len(prefix) + end:].strip():
                        serial_parse_notes.append({'prefix': prefix, 'note': 'Valid first JSON object followed by interleaved console bytes; trailing bytes not used.'})
                except json.JSONDecodeError:
                    if dest is not observations:
                        raise
                    serial_parse_notes.append({'prefix': prefix, 'note': 'Interleaved observer JSON could not be decoded; sample not used.'})
    assert [r['argv'][4] for r in records] == ['create', 'evidence', 'infer', 'check', 'show']
    assert all(r['returncode'] == 0 for r in records)
    stages = {r['argv'][4]: r for r in records}
    inferred, proposed = objects(stages['infer']['stdout'])
    checked, verified = objects(stages['check']['stdout'])
    shown, = objects(stages['show']['stdout'])
    assert verified == shown == inspections[-1]['tasks'][0]['result']
    assert inspections[-1]['list_returncode'] == 0 and inspections[-1]['processes'] == []
    state = shown['state']
    assert state['proposal']['arguments'] == {'text': '56'}
    assert state['phase'] == 'verified' and state['executed_actions'] == 0
    assert state['verification']['accepted'] is True
    assert state['verification']['authorizes_actions'] is False
    assert state['verification']['checker'] == 'integer-arithmetic-v1'
    assert checked['check'] == state['verification']
    raw = inferred['raw_model_output']
    assert raw == '<tool_call>\n{"name":"record_answer","arguments":{"text":"56"}}\n</tool_call>\n'
    native = inferred['guest_diagnostics']['native']
    assert native['returncode'] == 0 and native['raw_output'] == raw
    assert native['executed_actions'] == 0
    assert inferred['guest_diagnostics']['backend'] == 'avx2'
    checks = inferred['guest_diagnostics']['raw_model_checks']
    assert checks['prefix_sha256'] == validation['model_after']['sha256']
    assert checks['prefix_bytes_hashed'] == validation['model_after']['bytes']
    assert checks['fd_access_mode'] == 'O_RDONLY' and checks['blkroget'] == 1
    native_stderr = native['stderr']
    supervisor = dict((k, int(v)) for k, v in re.findall(r'(\w+)=(\d+)', re.search(r'ROKO_SUPERVISOR_USAGE ([^\n]+)', native_stderr)[1]))
    assert 'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1' in native_stderr
    native_limits = dict((k, int(v)) for k, v in re.findall(r'(\w+)=(\d+)', re.search(r'ROKO_GRANITE_LIMITS ([^\n]+)', native_stderr)[1]))
    resources = [r for r in observations if r.get('kind') == 'guest_resources']
    # The admitted native helper runs via its bundled ELF loader, whose comm is
    # ld-linux-x86-64. The observer includes it by the /runtime/granite argv path.
    helper_rows = [p for r in resources for p in r['processes'] if p['comm'] == 'ld-linux-x86-64']
    assert helper_rows
    assert max(p['VmRSS_bytes'] for p in helper_rows) == supervisor['peak_tree_rss_bytes']
    assert any(r.get('kind') == 'return' and r.get('exit_code') == 0 for r in observations)
    phases = [json.loads(line.split(' ', 1)[1]) for line in stages['infer']['stderr'].splitlines() if line.startswith('ROKO_GRANITE_GUEST_OBSERVATION ')]
    snapshots = [r for r in observations if r.get('kind') == 'snapshot']
    # Preserve actual observer records, without treating widget state as screenshot pixels.
    answer_snapshots = [r for r in snapshots if 'Proposed answer:\\n56' in json.dumps(r)]
    assert answer_snapshots
    jit = json.loads((RESULT / 'jit-observations.json').read_text())
    flush_counts = [int(re.search(r'TB flush count\s+(\d+)', r['qmp']['return'])[1]) for r in jit]
    pngs = {}
    for name in ['answer-first', 'care-during-native', 'closing-controls-later']:
        png, ppm = RESULT / (name + '.png'), RESULT / (name + '.ppm')
        a, b = Image.open(png), Image.open(ppm)
        assert a.mode == b.mode == 'RGB' and a.size == b.size == (1280, 800)
        assert a.tobytes() == b.tobytes()
        png.chmod(0o444)
        pngs[name] = {'png_path': str(png.relative_to(ROOT)), 'png_sha256': sha(png),
                      'ppm_sha256': sha(ppm), 'lossless_pixel_identity': True,
                      'capture_host_elapsed_seconds': validation['captures'][name]['elapsed_seconds'],
                      'human_pixels_actually_viewed': True}
    artifacts = {
        'actual_cli_records': save('actual-cli-records.json', records),
        'actual_post_close_inspection': save('actual-post-close-inspection.json', inspections[-1]),
        'native_output': save('native-output.txt', raw, raw=True),
        'native_stderr': save('native-stderr.txt', native_stderr, raw=True),
        'answer_widget_state': save('answer-widget-state.json', answer_snapshots[-1]),
    }
    stage = ROOT / 'build-src/companion-model-guest/stage-v2-compact'
    lock = json.loads((stage / 'manifest.json').read_text())
    for name, pin in lock['files'].items():
        assert sha(stage / name) == pin['sha256']
    command_bytes = (json.dumps(validation['command'], separators=(',', ':')) + '\n').encode()
    provenance = {
        'command': validation['command'],
        'command_sha256': hashlib.sha256(command_bytes).hexdigest(),
        'command_hash_format': 'UTF-8 compact JSON array with separators comma/colon and final newline',
        'runner': validation['source_sha256'],
        'cache_candidate_admission_sha256': sha(ROOT / 'boot/companion-model-guest-cache128/admission.json'),
        'guest_manifest_path': str((stage / 'manifest.json').relative_to(ROOT)),
        'guest_manifest_sha256': sha(stage / 'manifest.json'),
        'guest_source_recipe_hashes': lock['source_sha256'],
        'guest_file_pins': lock['files'],
        'exact_source_diff_hashes': {p.name: sha(p) for p in stage.glob('*.diff')},
        'assembly_sha256': sha(ROOT / 'build/companion-model-guest/attempt-3/assembly.json'),
        'bootstrap_sha256': sha(ROOT / 'build/companion-model-guest/attempt-3/bootstrap.cpio.gz'),
        'analysis_script_sha256': sha(Path(__file__)),
    }
    artifacts['provenance'] = save('provenance.json', provenance)
    report = {
        'passed': True,
        'scope': 'One actual graphical arithmetic interaction inside the COSMIC VM, actual bridge/CLI/provider/model/controller, rendered answer, responsive care control, normal close and immutable cleanup. Not broad correctness or target-hardware performance.',
        'task': state,
        'actual_cli_sequence': [{'stage': r['argv'][4], 'seconds': r['seconds'], 'timeout_seconds': r['timeout'], 'returncode': r['returncode']} for r in records],
        'request_seconds': inferred['seconds'],
        'request_observations': phases,
        'native_limits': native_limits,
        'native_max_rss_kib': native['native_max_rss_kib'],
        'native_major_faults': native['native_major_faults'],
        'supervisor_observations': supervisor,
        'guest_resource_samples': len(resources),
        'guest_minimum_observed_available_bytes': min(r['meminfo']['MemAvailable_bytes'] for r in resources),
        'native_helper_maximum_observed_rss_row': max(helper_rows, key=lambda r: r.get('VmRSS_bytes', 0)),
        'memory_caveat': 'Guest MemAvailable includes reclaimable mapped/file pages; it is not guaranteed additional inference headroom. No guest swap, cache dropping, balloon, or host setting change was used.',
        'host_peak_qemu_rss_kib': validation['peak_qemu_rss_kib'],
        'host_minimum_available_bytes': validation['minimum_host_available_bytes'],
        'host_available_floor_bytes': validation['host_available_floor_bytes'],
        'host_minimum_margin_above_floor_bytes': validation['minimum_host_available_bytes'] - validation['host_available_floor_bytes'],
        'tcg_cache_bound_mib': 128,
        'peak_anonymous_executable_resident_kib': validation['peak_anonymous_executable_rss_kib'],
        'maximum_observed_tb_flush_count': max(flush_counts),
        'cache_caveat': 'The paused diagnostic distinguished virtual reservation from RSS. This run measured resident anonymous executable memory consistent with the explicit cache bound. Runtime is not an isolated benchmark of the cache change: graphical workload and prompt also differ from the serial reference.',
        'screenshots': pngs,
        'visual_review': {
            'answer-first': 'Viewed actual character, proposed answer 56, independent check passed, task ID and no-external-actions text. Goal entry begins offscreen due horizontal scrolling. Disabled Cancel partly overlapped by dock.',
            'care-during-native': 'Viewed changed resting sprite and Resting quietly label while native inference was active; this supports working care input during inference, not smooth frame rate. Progress text behind the panel is partly occluded.',
            'closing-controls-later': 'Viewed reopened controls after closing Ask, then used Close avatar; observer returned0.'},
        'ui_final_state_evidence': 'Actual observer shows Ask enabled and Cancel disabled after answer. Observer records are separate from rendered pixel proof.',
        'observed_label_changes': [r for r in observations if r.get('kind') == 'label_text_changed'],
        'serial_parse_notes': serial_parse_notes,
        'normal_exit': {'avatar_returncode': 0, 'helper_processes_after_close': [], 'session_exit': 0, 'qemu_exit': 0,
                        'watchdog_fired': False, 'qemu_running_after_cleanup': False,
                        'procedure': 'Closed Ask, reopened care panel, clicked Close avatar, typed ci for genuine CLI/process inspection. Typed exit closed only terminal; reopened terminal and typed existing /usr/bin/roko-avatar-finish for normal COSMIC session exit.'},
        'immutable_model_sha256': validation['model_after']['sha256'],
        'immutable_root_sha256': validation['root_sha256_after'],
        'model_unchanged': True,
        'root_unchanged': True,
        'elapsed_host_seconds_including_cleanup': validation['elapsed_seconds'],
        'lifecycle_validation_sha256': sha(RESULT / 'validation.json'),
        'guest_stage_manifest_sha256': validation['cache_candidate_admission']['guest_stage_manifest_sha256'],
        'runner_sha256': validation['cache_candidate_admission']['runner_sha256'],
        'finite_bounds': {k: validation[k] for k in ('memory_mib', 'tcg_cpus', 'native_threads', 'vm_wall_seconds', 'guest_watchdog_seconds', 'bridge_seconds', 'provider_seconds', 'native_seconds', 'host_rss_cap_bytes', 'host_available_floor_bytes', 'disk_floor_bytes')},
        'native_limits_extra': {'tree_rss_cap_bytes': 5 * 1024**3, 'guest_available_floor_bytes': 512 * 1024**2, 'rlimit_as_bytes': 6 * 1024**3, 'startup_seconds': 120},
        'candidate_changes': 'Separate pinned bridge/UI timeout option up to1080 with default120 preserved; admitted raw-provider CLI guard; provider diagnostics moved to stderr only; read-only observations; outer graphical watchdog1410/host1500. Native900/provider930 and resource floors unchanged. Original stages and serial success preserved.',
        'prior_attempts': 'Attempts1 and2 remain host-memory-guard stops, not model-answer failures. No prior receipt or screenshot was overwritten.',
        'cancellation_coverage': 'Six harmless candidate tests include actual process cancellation/timeout through staged supervisor using an inert helper and detached child. This successful real inference was not canceled; no live-model UI cancellation pass is claimed.',
        'artifacts': artifacts,
        'harmless_tests_sha256': sha(RESULT / 'harmless-tests.txt'),
        'serial_sha256': sha(RESULT / 'serial.txt'),
    }
    result = save('analysis.json', report)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
