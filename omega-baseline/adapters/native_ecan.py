"""Actual ECAN attention-bank subset, ephemeral and advisory only.

No controller permissions, persistent state, scheduler, or tool execution is exposed.
Caller inputs are small trusted fixtures, never raw MeTTa. Upstream source is
required locally and is intentionally not redistributed by this project.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'd3a3c0e369df052e31992fcdbafdec4a42d1a3ad'
MODULES = (
    'attention/AttentionParam',
    'attention-bank/utilities/helper-functions',
    'attention-bank/attention-value/getter-and-setter',
    'attention-bank/bank/attention-bank',
    'attention-bank/bank/importance-index/importance-index',
    'attention-bank/bank/attentional-focus/attentional-focus',
    'attention-bank/utilities/recentVal',
)
class NativeECANError(RuntimeError):
    """Unavailable, altered, timed-out, or invalid native execution."""

def _validate(candidates, focus_size, timeout):
    if type(candidates) is not list or not 1 <= len(candidates) <= 16:
        raise ValueError('Expected 1..16 candidate dictionaries')
    if type(focus_size) is not int or not 1 <= focus_size <= 16:
        raise ValueError('focus_size must be an integer in 1..16')
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError('timeout must be an integer in 1..30 seconds')
    seen = set(); safe = []
    for item in candidates:
        if type(item) is not dict or set(item) != {'id', 'sti', 'lti', 'stimulus'}:
            raise ValueError('Each candidate requires exactly id, sti, lti, stimulus')
        identifier = item['id']
        if type(identifier) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,31}', identifier) is None or identifier in seen:
            raise ValueError('Candidate identifiers must be unique lowercase ASCII identifiers (1..32 characters)')
        for key, limit in [('sti', 1000), ('lti', 1000), ('stimulus', 10)]:
            if type(item[key]) is not int or not 0 <= item[key] <= limit:
                raise ValueError(f'{key} must be an integer in 0..{limit}')
        seen.add(identifier); safe.append(dict(item))
    return safe

def _program(candidates, focus_size):
    # Only fixed library names, generated symbols, and previously validated integers.
    # Candidate identifiers never enter executable source, even after validation.
    lines = ['!(import! &self (library lib_import))',
             '!(import_prolog_function working_dir)',
             '!(let $p (working_dir) (assertaPredicate (Predicate (library_path $p))))',
             '!(import! &self (library lib_he))', '!(import! &self (library lib_spaces))']
    lines += [f'!(import! &self (library metta-attention {module}))' for module in MODULES]
    lines += [f'!(updateAttentionParam MAX_AF_SIZE {focus_size})']
    for index, item in enumerate(candidates):
        lines += [f'!(setAv ecan_atom_{index} ({item["sti"]} {item["lti"]} 0))']
    for index, item in enumerate(candidates):
        lines += [f'!(stimulate ecan_atom_{index} {item["stimulus"]})']
    for index in range(len(candidates)):
        lines += [f'!(let* (($s (getSti ecan_atom_{index})) ($l (getLti ecan_atom_{index}))) (println! (ECAN_ROW {index} $s $l)))']
    lines += ['!(let $a (getAfAtoms) (println! (ECAN_FOCUS $a)))',
              '!(let* (($s (getAttentionParam FUNDS_STI)) ($l (getAttentionParam FUNDS_LTI))) (println! (ECAN_FUNDS $s $l)))']
    return '\n'.join(lines) + '\n'

def _parse(output, candidates, focus_size):
    output = re.sub(r'\x1b\[[0-9;]*m', '', output)
    number = r'(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
    matches = re.findall(r'^\(ECAN_ROW (\d+) '+number+' '+number+r'\)$', output, re.M)
    rows = {}
    for index, sti, lti in matches:
        index = int(index)
        if index in rows or index >= len(candidates): raise NativeECANError('Invalid native row identity')
        sti, lti = float(sti), float(lti)
        if not all(math.isfinite(x) and 0 <= x <= 1200 for x in (sti, lti)):
            raise NativeECANError('Invalid native attention value')
        rows[index] = {'id': candidates[index]['id'], 'sti': sti, 'lti': lti}
    focus = re.findall(r'^\(ECAN_FOCUS \(([^()]*)\)\)$', output, re.M)
    funds = re.findall(r'^\(ECAN_FUNDS '+number+' '+number+r'\)$', output, re.M)
    if len(rows) != len(candidates) or len(focus) != 1 or len(funds) != 1:
        raise NativeECANError('Incomplete or ambiguous native output')
    symbols = focus[0].split(); indices = []
    for symbol in symbols:
        match = re.fullmatch(r'ecan_atom_(\d+)', symbol)
        if not match or int(match[1]) not in rows: raise NativeECANError('Invalid native focus identity')
        indices.append(int(match[1]))
    if len(indices) != len(set(indices)) or len(indices) > focus_size:
        raise NativeECANError('Invalid native focus size')
    for index, row in rows.items(): row['in_focus'] = index in indices
    funds_sti, funds_lti = map(float, funds[0])
    if not all(math.isfinite(x) and 0 <= x <= 100000 for x in (funds_sti, funds_lti)):
        raise NativeECANError('Invalid native funds')
    if abs(funds_sti + sum(r['sti'] for r in rows.values()) - 100000) > 1e-6 or abs(funds_lti + sum(r['lti'] for r in rows.values()) - 100000) > 1e-6:
        raise NativeECANError('Native attention-bank conservation failed')
    return {'implementation': 'native-metta-ecan-attention-bank-subset', 'commit': COMMIT,
            'advisory_only': True, 'authorizes_actions': False, 'persistent_state_changed': False,
            'ranking': sorted(rows.values(), key=lambda row: (-row['sti'], -row['lti'], row['id'])),
            'focus': sorted(candidates[i]['id'] for i in indices),
            'funds': {'sti': funds_sti, 'lti': funds_lti}}

def rank_candidates(candidates, *, focus_size=4, timeout=10, root=ROOT):
    """Return detached advisory ranking from a fresh actual native ECAN bank.

    Requires manually acquired pinned source and existing runtime. Does not
    mutate candidate data, persist attention, authorize, schedule, or execute actions.
    """
    candidates = _validate(candidates, focus_size, timeout)
    root = Path(root).resolve()
    try: lock = json.loads((root/'metta-attention-source.lock.json').read_text())
    except (OSError, ValueError) as exc: raise NativeECANError('Native ECAN source lock is unavailable') from exc
    if lock.get('commit') != COMMIT: raise NativeECANError('Unexpected native ECAN source commit')
    source = root/'build-src/metta-attention-research'
    if not source.is_dir(): raise NativeECANError('Native ECAN source is missing; it is excluded from archives because redistribution rights are unknown')
    python = root/'.venv/bin/python'; runner = root/'vendor/PeTTa-omega-release/run.sh'
    if not python.is_file() or not runner.is_file() or not (root/'runtime/swipl/bin/swipl').is_file():
        raise NativeECANError('Native ECAN requires the existing local Python, PeTTa v1.0.4, and SWI-Prolog runtime')
    with tempfile.TemporaryDirectory(prefix='ecan-advisory-', dir=root) as directory:
        work = Path(directory); copy = work/'metta-attention'; copy.mkdir()
        for module in MODULES:
            name = module+'.metta'; path = source/name
            try: data = path.read_bytes()
            except OSError as exc: raise NativeECANError('Native ECAN module is missing: '+name) from exc
            if hashlib.sha256(data).hexdigest() != lock['files'].get(name):
                raise NativeECANError('Native ECAN source hash mismatch: '+name)
            destination = copy/name; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(data)
        program = copy/'advisory.metta'; program.write_text(_program(candidates, focus_size))
        site = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_paths()["purelib"])'], text=True, timeout=5).strip()
        env = {'PATH':str(root/'runtime/swipl/bin')+':/usr/bin:/bin', 'HOME':directory, 'TMPDIR':directory,
               'PYTHONHOME':sys.base_prefix, 'LD_LIBRARY_PATH':str(Path(sys.base_prefix)/'lib'), 'PYTHONPATH':site,
               'HF_HUB_OFFLINE':'1', 'TRANSFORMERS_OFFLINE':'1', 'OMP_NUM_THREADS':'1'}
        command = [str(python), str(root/'scripts/no-network.py'), 'sh', str(runner), str(program)]
        process = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True, close_fds=True)
        try: out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL); process.communicate()
            raise NativeECANError('Native ECAN process timed out') from exc
        if process.returncode or 'ERROR:' in out+err or '❌' in out+err:
            raise NativeECANError('Native ECAN process failed; no ranking returned')
        return _parse(out, candidates, focus_size)
