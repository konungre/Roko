"""Real third-turn restart and replay probe; copies the verified synthetic DB."""
import argparse,hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from recovered import render,system_message

def audit(root):
    def receipt(name):
        return next(json.loads(x.split(' ',1)[1]) for x in (root/name).read_text().splitlines()
                    if x.startswith('ROKO_FRESH_CONVERSATION '))
    replies=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
    native=receipt('stderr.txt');replay=receipt('replay.stderr.txt')
    saved=json.loads((root/'replay.stdout.txt').read_text())
    with sqlite3.connect(root/'history.sqlite') as db:
        ledger=json.loads(db.execute("SELECT cognitive_history FROM sessions WHERE id='language'").fetchone()[0])
    request=json.loads((root/'requests.jsonl').read_text().splitlines()[1])
    system=system_message(SimpleNamespace(context=[],cognitive_context=ledger))
    prompt=render([{'role':'system','content':system}]+replies[0]['history']+[{'role':'user','content':request['text']}])
    checks={'revision_two_loaded':replies[0]['revision']==2 and len(replies[0]['history'])==4,
        'third_turn_committed':replies[1].get('status')=='completed' and replies[1]['revision']==3 and len(replies[2]['history'])==6,
        'native_mork_complete_history':len(native['mork_receipts'])==1 and native['mork_receipts'][0]['indexed_messages']==4 and not native['mork_receipts'][0]['history_omitted'],
        'both_observations_restored':len(ledger)==2 and native['cognitive_history']==ledger,
        'native_model_prompt_binding':len(native['native_calls'])==1 and native['native_calls'][0]['prompt_sha256']==hashlib.sha256(prompt.encode()).hexdigest(),
        'native_model_verified':native['native_calls'][0].get('model_verified_before_history_commit') is True,
        'no_new_nars_inference':native['cognitive_receipts']==[],
        'recall_both_creatures':all(x in replies[1]['text'].lower() for x in ('fox','robin')),
        'exact_restart_replay':saved==replies[1],
        'replay_no_native_work':all(replay[k]==[] for k in ('native_calls','mork_receipts','cognitive_receipts','ecan_receipts'))}
    result={'passed':all(checks.values()),'checks':checks,'reply':replies[1],'native_seconds':native['native_calls'][0]['seconds'],'executed_actions':0}
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path);p.add_argument('--source-db',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--audit-only',action='store_true')
    a=p.parse_args();root=a.output.resolve()
    if not a.audit_only:
        if not a.profile or not a.source_db:p.error('profile and source-db required')
        root.mkdir(mode=0o700,parents=True,exist_ok=False)
        with sqlite3.connect(a.source_db.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(root/'history.sqlite') as dst:src.backup(dst)
        snapshot=dict(api_version=2,op='snapshot',session_id='language')
        turn=dict(api_version=2,op='turn',session_id='language',request_id='language-3',expected_revision=2,text='Which two creatures did we discuss? Answer in one short sentence.',context=[],max_output_tokens=64)
        env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
        for prefix,requests in (('',[snapshot,turn,snapshot]),('replay.',[turn])):
            data=''.join(json.dumps(x)+'\n' for x in requests)
            (root/('replay.jsonl' if prefix else 'requests.jsonl')).write_text(data)
            with (root/(prefix+'stdout.txt')).open('wb') as out,(root/(prefix+'stderr.txt')).open('wb') as err:
                subprocess.run([sys.executable,'-B',str(SOURCE/'durable_server.py')],input=data.encode(),stdout=out,stderr=err,env=env,timeout=240,check=True)
    result=audit(root);print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
