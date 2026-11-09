#!/usr/bin/env python3
"""Launch the real bounded Omega worker, or check its explicit runtime inputs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def preflight(env):
    missing = []
    for name, suffixes in {
        'PETTA_PATH': ['src/metta.pl'],
        'OMEGA_PATH': ['src/loop.metta', 'src/utils.py'],
        'ROKO_RUNTIME_ROOT': ['granite-model.lock.json', 'runtime/granite/omega-granite-infer',
                              'metta-attention-source.lock.json', 'build-src/metta-attention-research',
                              '.venv/bin/python', 'vendor/PeTTa-omega-release/run.sh',
                              'runtime/swipl/bin/swipl'],
    }.items():
        if not env.get(name):
            missing.append(name)
        else:
            missing += [str(Path(env[name]) / suffix) for suffix in suffixes
                        if not (Path(env[name]) / suffix).exists()]
    root = Path(env['ROKO_RUNTIME_ROOT']) if env.get('ROKO_RUNTIME_ROOT') else None
    if root and (root / 'granite-model.lock.json').is_file():
        try:
            lock = json.loads((root / 'granite-model.lock.json').read_text())
            required = [root / lock['path']]
            required += [root / lock['tokenizer_path'] / name for name in lock['tokenizer_files']]
            missing += [str(path) for path in required if not path.is_file()]
        except (ValueError, KeyError, TypeError):
            missing.append('valid granite-model.lock.json')
    if not shutil.which(env.get('ROKO_SWIPL', 'swipl')):
        missing.append('ROKO_SWIPL executable')
    return missing


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--probe', action='store_true', help='run two real free-form conversation turns')
    args = parser.parse_args()
    env = dict(os.environ)
    env['PYTHONPATH'] = str(HERE) + os.pathsep + env.get('PYTHONPATH', '')
    env['ROKO_CONVERSATION_STEP'] = str(HERE / 'step.metta')
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    missing = preflight(env)
    if missing:
        print(json.dumps({'status': 'blocked', 'missing': missing, 'native_turns': 0}), file=sys.stderr)
        return 2
    if args.check:
        print(json.dumps({'status': 'paths-present', 'native_qualified': False}))
        return 0
    command = [env.get('ROKO_SWIPL', 'swipl'), '--stack_limit=512m', '--table-space=512m',
               '-q', '-s', str(HERE / 'worker.pl')]
    if not args.probe:
        return subprocess.call(command, env=env)
    context = [dict(id='project', text='The user is writing a short story about a lighthouse.',
                    sti=100, lti=20, stimulus=2)]
    turns = [dict(text='I am stuck on my writing project. Can we talk about a small next step?', context=context),
             dict(text='How could that fit the setting I mentioned?', context=context)]
    result = subprocess.run(command, env=env, input=''.join(json.dumps(t)+'\n' for t in turns),
                            text=True, capture_output=True, timeout=240)
    sys.stderr.write(result.stderr)
    if result.returncode:
        return result.returncode
    replies = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    if len(replies) != 2 or any(not r.get('text') or r.get('executed_actions') != 0 for r in replies):
        raise ValueError('Native conversational output contract failed')
    print(json.dumps({'status': 'native-transport-completed', 'turns': replies,
                      'semantic_review_required': True}, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
