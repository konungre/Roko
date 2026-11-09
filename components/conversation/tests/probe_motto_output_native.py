"""Native regression: incompatible Granite output cannot poison durable history."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from durable_store import Store


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    db=args.output.resolve()/'history.sqlite';started=time.monotonic()
    def request(identifier,text):
        return {'api_version':2,'op':'turn','session_id':'output-roundtrip','request_id':identifier,
                'expected_revision':0,'text':text,'context':[],'max_output_tokens':64}
    first=request('incompatible','Write a Python escaped newline as a backslash followed by lowercase n. Do not use a real newline. Reply briefly.')
    second=request('retry','What is two plus three? Reply in one short sentence.')
    def run(label,requests):
        with (args.output/(label+'.stderr')).open('xb') as err:
            proc=subprocess.run([sys.executable,'-B',str(SOURCE/'durable_server.py')],
                input=b''.join(json.dumps(r).encode()+b'\n' for r in requests),stdout=subprocess.PIPE,stderr=err,
                env={**os.environ,'ROKO_FRESH_PROFILE':args.profile,'ROKO_HISTORY_DB':str(db)},timeout=240)
        (args.output/(label+'.stdout')).write_bytes(proc.stdout)
        if proc.returncode:raise ValueError('Native server failed')
        replies=[json.loads(row) for row in proc.stdout.splitlines()]
        records=[json.loads(row.split(' ',1)[1]) for row in (args.output/(label+'.stderr')).read_text().splitlines()
                 if row.startswith('ROKO_FRESH_CONVERSATION ')]
        if len(replies)!=len(requests) or len(records)!=1:raise ValueError('Native protocol count')
        return replies,records[0]
    replies,record=run('turns',[first,second])
    replay,replay_record=run('restart',[second])
    with Store(db) as store:state=store.snapshot('output-roundtrip')
    native=record['native_calls'];motto=record['motto_receipts']
    checks={
        'actual_model_produced_literal_backslash_n':len(native)==2 and '\\n' in native[0].get('stdout',''),
        'first_reply_not_committed':replies[0]['status']=='error',
        'next_request_completed':replies[1]['status']=='completed' and replies[1]['revision']==1,
        'failed_then_passed_motto':len(motto)==2 and [r['status'] for r in motto]==['failed','passed'],
        'history_contains_only_retry':state['revision']==1 and len(state['history'])==2 and state['history'][0]['content']==second['text'],
        'restart_replay_without_inference':replay==[replies[1]] and not replay_record['native_calls'] and not replay_record['motto_receipts'],
    }
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'replies':replies,
            'seconds':time.monotonic()-started,'executed_actions':0}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return int(result['status']!='passed')


if __name__=='__main__':raise SystemExit(main())
