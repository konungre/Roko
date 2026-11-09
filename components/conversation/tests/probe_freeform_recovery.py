"""Real free-form conversation survives input admission failure in one worker."""
import argparse,json,os,subprocess,sys
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.output.resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
    def turn(rid,rev,text,context=[]):return dict(api_version=2,op='turn',session_id='garden',request_id=rid,expected_revision=rev,text=text,context=context,max_output_tokens=64)
    context=[dict(id='tone',text='Use a calm, practical tone.',sti=100,lti=10,stimulus=0)]
    first=turn('first',0,'I am planning a small balcony garden. I prefer herbs, have morning sun, and can water twice a week. Suggest two plants in one sentence.',context)
    last=turn('third',2,'Give one short next step based on my preferences.')
    requests=[first,turn('overflow',1,'a b '*1000),turn('second',1,'What watering schedule and sunlight did I mention?'),last,last,dict(api_version=2,op='snapshot',session_id='garden')]
    data=''.join(json.dumps(x)+'\n' for x in requests);(root/'requests.jsonl').write_text(data)
    env={**os.environ,'ROKO_FRESH_PROFILE':str(a.profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
    with (root/'stdout.txt').open('wb') as out,(root/'stderr.txt').open('wb') as err:
        proc=subprocess.run([sys.executable,'-B',str(SOURCE/'durable_server.py')],input=data.encode(),stdout=out,stderr=err,env=env,timeout=600)
    replies=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
    record=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
    checks={'protocol':proc.returncode==0 and len(replies)==6,'first_complete':replies[0].get('status')=='completed',
        'real_ecan':len(record['ecan_receipts'])==1 and replies[0].get('context_ids')==['tone'],
        'overflow_explicit':replies[1].get('code')=='context_limit',
        'same_revision_continues':replies[2].get('revision')==2 and replies[2].get('status')=='completed',
        'recall':all(x in replies[2].get('text','').lower() for x in ('twice','morning')),
        'third_complete':replies[3].get('revision')==3 and replies[3].get('status')=='completed',
        'exact_replay':replies[4]==replies[3],
        'no_failed_message_committed':len(replies[5]['history'])==6 and all(x['content']!='a b '*1000 for x in replies[5]['history']),
        'ordinary_prose_no_nars':record['cognitive_receipts']==[] and record['cognitive_history']==[],
        'native_mork_each_claim':len(record['mork_receipts'])==4,'native_calls':len(record['native_calls'])==4,
        'successful_models_verified':all(x.get('model_verified_before_history_commit') is True for x in record['native_calls'] if x['returncode']==0)}
    result={'passed':all(checks.values()),'checks':checks,'replies':replies,'executed_actions':0}
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
