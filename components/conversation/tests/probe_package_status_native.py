"""Real unavailable/restored evidence and expired admission in ordinary turns.

Only a marked disposable receipt copy is changed; canonical source is untouched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from durable_store import Store


def main():
    p=argparse.ArgumentParser()
    for name in ('profile','expired-profile','source-copy','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    profile=json.loads(a.profile.read_bytes());manifest=json.loads(Path(profile['package_awareness']['manifest']).read_bytes())
    data=Path(manifest['receipts_path']);copy_root=a.source_copy.resolve()
    if (not copy_root.name.startswith('package-status-source-') or data.parent!=copy_root or data.is_symlink()
            or not (copy_root/'.disposable-receipt-fixture').is_file()):
        raise ValueError('Refuse to alter unmarked/canonical source')
    original=data.read_bytes()
    if (copy_root/'.disposable-receipt-fixture').read_text().strip()!=hashlib.sha256(original).hexdigest():
        raise ValueError('Disposable fixture marker mismatch')
    db=a.output/'history.sqlite';started=time.monotonic()
    def request(rid,revision,text,session='limits'):
        return dict(api_version=2,op='turn',session_id=session,request_id=rid,expected_revision=revision,text=text,context=[],max_output_tokens=96)
    first=request('missing',0,'Can you determine current packages or the running system from the package evidence? Reply briefly.')
    second=request('restored',1,'Which source revision and machine does the restored imported record mention? Is its observation time known? Reply briefly.')
    third=request('missing-again',2,'The receipt file is unavailable again. Does that imply packages are absent, or make the earlier record current running-system evidence? Reply briefly.')
    expired=request('expired',0,'The local admission expired. Can you use the receipt as current evidence, and do you know the actual source observation age? Reply briefly.','expired')
    records=[]
    def start(label,profile_path):
        err=(a.output/(label+'.stderr')).open('xb')
        proc=subprocess.Popen([sys.executable,'-B',str(SOURCE/'durable_server.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0,
            env={**os.environ,'ROKO_FRESH_PROFILE':str(profile_path.resolve()),'ROKO_HISTORY_DB':str(db)})
        return proc,err,bytearray()
    def exchange(worker,row):
        proc,_,captured=worker;proc.stdin.write(json.dumps(row).encode()+b'\n');proc.stdin.flush()
        raw=b'';deadline=time.monotonic()+200
        while not raw.endswith(b'\n'):
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([proc.stdout],[],[],remaining)[0]:raise TimeoutError('Native reply deadline')
            chunk=os.read(proc.stdout.fileno(),1)
            if not chunk or len(raw)>131072:raise ValueError('Native reply incomplete/oversized')
            raw+=chunk
        captured.extend(raw);return json.loads(raw)
    def stop(label,worker):
        proc,err,captured=worker
        proc.stdin.close();proc.stdin=None
        try:rest,_=proc.communicate(timeout=30)
        finally:err.close()
        captured.extend(rest);(a.output/(label+'.stdout')).write_bytes(captured)
        if proc.returncode:raise ValueError('Native server failed')
        parsed=[json.loads(row.split(' ',1)[1]) for row in (a.output/(label+'.stderr')).read_text().splitlines() if row.startswith('ROKO_FRESH_CONVERSATION ')]
        if len(parsed)!=1:raise ValueError('Native final receipt count')
        records.append(parsed[0]);return parsed[0]
    worker=None;label=None
    try:
        data.unlink();label='availability';worker=start(label,a.profile)
        replies=[exchange(worker,first)]
        data.write_bytes(original);replies.append(exchange(worker,second))
        data.unlink();replies.append(exchange(worker,third));record=stop(label,worker);worker=None
        data.write_bytes(original);label='expired';worker=start(label,a.expired_profile)
        expired_reply=exchange(worker,expired);expired_record=stop(label,worker);worker=None
        data.unlink();label='restart';worker=start(label,a.profile)
        replay=[exchange(worker,row) for row in (first,second,third)]
        replay_record=stop(label,worker);worker=None
    finally:
        if worker is not None:
            proc,err,_=worker
            proc.terminate()
            try:proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.communicate(timeout=3)
            err.close()
        data.write_bytes(original)
    states=[row.get('package_state',{}) for row in replies];old=expired_reply.get('package_state',{})
    with Store(db) as store:
        history=store.snapshot('limits',include_cognition=True);expired_state=store.snapshot('expired',include_cognition=True)
    query_records=[r for r in record['package_awareness_receipts'] if r.get('stage_kind')!='evidence_status']
    checks={
        'ordinary_turns_completed':all(r['status']=='completed' for r in replies) and expired_reply['status']=='completed',
        'missing_is_no_admitted_source':all(states[i].get('evidence_status')=='source_missing' and states[i].get('source') is None and states[i].get('data_admitted') is False for i in (0,2)),
        'restored_source_admitted_without_freshness_claim':states[1].get('evidence_status')=='available_freshness_unknown' and states[1].get('source_observation_time_known') is False and states[1].get('source',{}).get('source_revision')==3,
        'last_known_source_is_historical':states[2].get('last_known_source') is not None and states[2].get('source') is None and states[2].get('query_receipt_sha256') is None,
        'one_native_query_after_restore':len(query_records)==1 and query_records[0]['status']=='passed',
        'expired_admission_not_observation_age':old.get('evidence_status')=='admission_expired' and old.get('availability')=='available' and old.get('source_observation_time_known') is False and old.get('source') is None,
        'no_query_for_expired':all(r.get('stage_kind')=='evidence_status' for r in expired_record['package_awareness_receipts']),
        'no_mutation_authority':all(s.get('mutation_authority') is False and s.get('executed_actions')==0 for s in states+[old]),
        'full_history_preserved':history['revision']==3 and len(history['history'])==6 and history['history'][0]['content']==first['text'] and history['history'][4]['content']==third['text'],
        'cognitive_ledger_unchanged':history['cognitive_history']==[] and expired_state['cognitive_history']==[],
        'restart_replays_while_source_missing':replay==replies and not replay_record['native_calls'] and not replay_record['package_awareness_receipts'] and not replay_record['motto_receipts'],
        'no_implicit_projection':not record['token_counter_calls'] and not expired_record['token_counter_calls'] and all('model_context' not in r for r in replies+[expired_reply]),
    }
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'replies':replies,'expired_reply':expired_reply,
            'seconds':time.monotonic()-started,'executed_actions':0,'native_nix_reexecuted_here':False,
            'expired_admission_time_is_test_fixture':True,'canonical_source_modified':False}
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return int(result['status']!='passed')


if __name__=='__main__':raise SystemExit(main())
