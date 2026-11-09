#!/usr/bin/env python3
"""Real PeTTa/Omega/Granite/MORK restart and cancellation probe; no doubles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def group_rows(group):
    rows = []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')',1)[1].split()
            if int(fields[2]) == group and fields[0] != 'Z':
                rows.append({'pid':int(path.parent.name),'start':fields[19]})
        except (OSError,ValueError): pass
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    config = profile['durable_memory']
    if Path(config['database']).exists():
        raise ValueError('Probe requires a new database; never overwrite prior history')
    args.output.mkdir(parents=True,exist_ok=False)
    source = Path(__file__).resolve().parent
    sys.path.insert(0,str(source.parents[1]/'mork-recovery-v1/source'))
    from conversation_store import ConversationStore
    def snapshot():
        store = ConversationStore(config['database'])
        try:
            result = store.snapshot(config['session'])
            result['open_requests'] = store.db.execute(
                "SELECT count(*) FROM conversation_requests WHERE session=? AND state IN ('pending','prepared')",
                (config['session'],)).fetchone()[0]
            return result
        finally:store.close()
    env = {**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve())}
    command = [profile['python'],'-B',str(source/'fresh_server.py')]
    reports = []
    def run(name, requests):
        directory = args.output/name
        directory.mkdir()
        (directory/'requests.json').write_text(json.dumps(requests,indent=2)+'\n')
        started = time.monotonic()
        with (directory/'stderr.txt').open('wb') as err:
            proc = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=env)
            try:
                out,_ = proc.communicate((''.join(json.dumps(r)+'\n' for r in requests)).encode(),timeout=240)
            except BaseException:
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise
        (directory/'stdout.txt').write_bytes(out)
        receipts = [json.loads(line.split(' ',1)[1]) for line in (directory/'stderr.txt').read_text().splitlines()
                    if line.startswith('ROKO_FRESH_CONVERSATION ')]
        replies = [json.loads(line) for line in out.decode().splitlines()]
        result = {'phase':name,'returncode':proc.returncode,'seconds':round(time.monotonic()-started,3),
                  'replies':replies,'receipts':receipts,'snapshot':snapshot()}
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        reports.append(result)
        print(json.dumps({'phase':name,'returncode':proc.returncode,
                          'revision':result['snapshot']['revision'],'seconds':result['seconds']}),flush=True)
        if proc.returncode != 0:raise RuntimeError('Native worker failed; see preserved '+name)
        return result
    first = run('first-process',[{'text':'I am writing a story set in a lighthouse. Suggest one short opening sentence.','context':[]}])
    second = run('restarted-process',[{'text':'What setting did I mention? Answer in one sentence.','context':[]}])
    # Cancel a third real inference after observing both supervisor and child.
    before = snapshot()
    directory = args.output/'cancelled-process'
    directory.mkdir()
    supervisor = None
    with (directory/'stdout.txt').open('wb') as out,(directory/'stderr.txt').open('wb') as err:
        proc = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
        try:
            proc.stdin.write(b'{"text":"Write another short opening sentence.","context":[]}\n')
            proc.stdin.flush()
            deadline = time.monotonic()+90
            observed = []
            while time.monotonic()<deadline and proc.poll() is None:
                for line in (directory/'stderr.txt').read_text().splitlines():
                    if line.startswith('ROKO_NATIVE_STARTED '):
                        supervisor = json.loads(line.split(' ',1)[1])['supervisor_pid']
                observed = group_rows(supervisor) if supervisor else []
                if len(observed)>=2:break
                time.sleep(.1)
            proc.send_signal(signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        finally:
            proc.stdin.close()
            if proc.poll() is None:proc.kill();proc.wait()
    deadline = time.monotonic()+10
    while supervisor and group_rows(supervisor) and time.monotonic()<deadline:time.sleep(.05)
    after = snapshot()
    cancellation = {'native_group_before':observed,
                    'native_group_after':group_rows(supervisor) if supervisor else [],
                    'answer_bytes':(directory/'stdout.txt').stat().st_size,
                    'history_unchanged':before['history_sha256']==after['history_sha256']}
    cancellation['passed'] = (len(observed)>=2 and not cancellation['native_group_after'] and
                              cancellation['answer_bytes']==0 and cancellation['history_unchanged'])
    (directory/'result.json').write_text(json.dumps(cancellation,indent=2)+'\n')
    cleanup = run('restart-after-cancel',[])
    def native_turn(report, expected_revision):
        if len(report['replies'])!=1 or len(report['receipts'])!=1:return False
        response, receipt = report['replies'][0],report['receipts'][0]
        mork, model = receipt['mork_receipts'],receipt['native_calls']
        return (set(response)=={'text','context_ids','executed_actions'} and
                response['executed_actions']==0 and response['context_ids']==[] and
                len(model)==1 and model[0]['returncode']==0 and
                model[0].get('model_verified_before_history_commit') and
                'descendants_cleaned=1' in model[0]['stderr'] and
                len(mork)==1 and mork[0]['revision']==expected_revision and
                len(mork[0]['evidence'])==expected_revision and
                mork[0]['native']['implementation']=='native-mork-rebuild-bounded-facts')
    passed = (native_turn(first,0) and native_turn(second,2) and
              'lighthouse' in second['replies'][0]['text'].lower() and
              second['snapshot']['revision']==4 and cancellation['passed'] and
              cleanup['snapshot']['history_sha256']==before['history_sha256'] and
              cleanup['snapshot']['open_requests']==0)
    summary = {'passed':bool(passed),'native_restart_continuity':bool(native_turn(second,2)),
               'lighthouse_recall':'lighthouse' in second['replies'][0]['text'].lower(),
               'cancellation':cancellation,'committed_messages':cleanup['snapshot']['revision'],
               'open_requests_after_restart':cleanup['snapshot']['open_requests'],
               'external_actions_dispatched':0,'python_fallback':False,
               'profile_sha256':hashlib.sha256(args.profile.read_bytes()).hexdigest(),
               'native_manifest_sha256':config['manifest_sha256']}
    (args.output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    return 0 if passed else 1


if __name__ == '__main__':raise SystemExit(main())
