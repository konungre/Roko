"""Real Omega/v2/Motto/Granite turns, restart replay and fail-closed input."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from durable_store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    db = args.output.resolve() / 'history.sqlite'
    started = time.monotonic()
    def turn(request_id, revision, text):
        return dict(api_version=2, op='turn', session_id='motto', request_id=request_id,
                    expected_revision=revision, text=text, context=[], max_output_tokens=64)
    first = turn('first', 0, 'Remember this fictional codeword: violet. Reply briefly.')
    second = turn('second', 1, 'What fictional codeword did I give you?')
    bad = turn('normalized', 2, r'Preserve this literal sequence: x\ny')
    recovery = turn('recovery', 2, 'What is two plus three? Reply briefly.')
    def run(label, requests):
        with (args.output / (label + '.stderr')).open('xb') as stderr:
            proc = subprocess.run([sys.executable, '-B', str(SOURCE / 'durable_server.py')],
                input=b''.join(json.dumps(row).encode() + b'\n' for row in requests),
                stdout=subprocess.PIPE, stderr=stderr, timeout=300,
                env={**os.environ, 'ROKO_FRESH_PROFILE':args.profile, 'ROKO_HISTORY_DB':str(db)})
        (args.output / (label + '.stdout')).write_bytes(proc.stdout)
        if proc.returncode:
            raise RuntimeError('Native server failed: ' + label)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        records = [json.loads(line.split(' ', 1)[1]) for line in
                   (args.output / (label + '.stderr')).read_text().splitlines()
                   if line.startswith('ROKO_FRESH_CONVERSATION ')]
        if len(records) != 1 or len(replies) != len(requests):
            raise ValueError('Native response count')
        return replies, records[0]
    replies, record = run('turns', [first, second, bad, recovery])
    replay, replay_record = run('restart', [first, second, recovery])
    with Store(db) as store:
        state = store.snapshot('motto')
    checks = {
        'three_completed_turns':all(replies[i]['status']=='completed' for i in (0,1,3)),
        'native_history_recall':'violet' in replies[1]['text'].lower(),
        'normalization_failed':replies[2]['status']=='error',
        'three_model_calls':len(record['native_calls'])==3,
        'motto_receipts':len(record['motto_receipts'])==4 and
            [r['status'] for r in record['motto_receipts']]==['passed','passed','failed','passed'],
        'atomic_revision_after_failure':state['revision']==3 and len(state['history'])==6,
        'restart_replay':replay==[replies[i] for i in (0,1,3)],
        'replay_no_native_calls':not replay_record['native_calls'] and not replay_record['motto_receipts'],
    }
    result = {'status':'passed' if all(checks.values()) else 'failed', 'checks':checks,
              'replies':replies,'seconds':time.monotonic()-started,'executed_actions':0}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return int(result['status']!='passed')


if __name__ == '__main__':
    raise SystemExit(main())
