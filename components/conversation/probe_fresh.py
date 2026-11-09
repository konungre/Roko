#!/usr/bin/env python3
"""Finite actual native JSON-lines probe; writes new, non-overwritten receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    requests = [{'text':'I am writing a story set in a lighthouse. Suggest one short opening sentence.', 'context':[]},
                {'text':'What setting did I mention? Answer in one sentence.', 'context':[]}]
    (args.output/'requests.json').write_text(json.dumps(requests,indent=2))
    started = time.monotonic()
    with (args.output/'stderr.txt').open('wb') as err:
        proc = subprocess.Popen([sys.executable,'-B',str(source/'fresh_server.py')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                env={**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve())})
        try:
            out, _ = proc.communicate(('\n'.join(json.dumps(x) for x in requests)+'\n').encode(),timeout=420)
        except BaseException:
            proc.terminate()
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise
    (args.output/'stdout.txt').write_bytes(out)
    parse_error = None
    try:
        replies = [json.loads(line) for line in out.decode().splitlines()]
    except (ValueError, UnicodeError) as error:
        replies = []
        parse_error = str(error)
    diagnostics = (args.output/'stderr.txt').read_text()
    receipts = [json.loads(line.removeprefix('ROKO_FRESH_CONVERSATION ')) for line in diagnostics.splitlines()
                if line.startswith('ROKO_FRESH_CONVERSATION ')]
    schema_ok = len(replies)==2 and all(set(r)=={'text','context_ids','executed_actions'}
                  and isinstance(r['text'],str) and r['text'].strip()
                  and r['context_ids']==[] and r['executed_actions']==0 for r in replies)
    native_ok = len(receipts)==1 and len(receipts[0]['native_calls'])==2 and all(
        r['returncode']==0 and r.get('model_verified_before_history_commit')
        and 'descendants_cleaned=1' in r['stderr'] for r in receipts[0]['native_calls'])
    result = {'returncode':proc.returncode, 'seconds':round(time.monotonic()-started,3),
              'schema_ok':schema_ok,'native_ok':native_ok, 'parse_error':parse_error,
              'lighthouse_recall':len(replies)==2 and 'lighthouse' in replies[1]['text'].lower(),
              'graphical_ui_tested':False, 'ecan_qualified':False,
              'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
                               if p.suffix in ('.py','.pl','.metta','.cpp')},
              'profile_sha256':hashlib.sha256(args.profile.read_bytes()).hexdigest()}
    result['passed'] = proc.returncode==0 and schema_ok and native_ok and result['lighthouse_recall']
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
