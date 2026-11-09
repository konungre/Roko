"""Qualify bounded eight-exchange history from a verified six-turn checkpoint.

Explicitly runs two new native generations, not eight exchanges from empty.
Audit-only checks captured evidence without opening a database or running a model.
"""
import argparse,hashlib,json,os,pathlib,sqlite3,subprocess,sys

def read_state(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT revision,history,cognitive_history,pending FROM sessions WHERE id='language'").fetchone()
    if row is None:raise ValueError('Missing language fixture')
    return dict(revision=row[0],history=json.loads(row[1]),cognitive_history=json.loads(row[2]),pending=row[3])

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def outputs(root,name):return [json.loads(x) for x in (root/(name+'stdout.txt')).read_text().splitlines()]
def receipt(root,name):
    rows=[json.loads(x.split(' ',1)[1]) for x in (root/(name+'stderr.txt')).read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION ')]
    if len(rows)!=1:raise ValueError('Expected one final native receipt')
    return rows[0]

def requests():
    long=dict(api_version=2,op='turn',session_id='language',request_id='long-default',expected_revision=6,
        text='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4,
        context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)],max_output_tokens=32)
    seven={**long,'request_id':'long-optin','context_policy':'extractive_v1'}
    eight=dict(api_version=2,op='turn',session_id='language',request_id='eighth-optin',expected_revision=7,
        text='Name both creatures.',context=[],max_output_tokens=32,context_policy='extractive_v1')
    default={k:v for k,v in eight.items() if k!='context_policy'};default['request_id']='default-after-seven'
    snapshot=dict(api_version=2,op='snapshot',session_id='language')
    return [long,snapshot,seven,default,snapshot,eight,dict(api_version=2,op='limits',session_id='language'),
            {**eight,'request_id':'ninth-optin','expected_revision':8},snapshot,eight]

def run(root,profile,source):
    root.mkdir(mode=0o700,parents=True,exist_ok=False)
    before=read_state(source)
    if before['revision']!=6 or len(before['history'])!=12 or len(before['cognitive_history'])!=2 or before['pending'] is not None:
        raise ValueError('Requires verified six-turn language checkpoint with two observations and no pending claim')
    save(root/'before.json',before)
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(root/'history.sqlite') as dst:src.backup(dst)
    env={**os.environ,'ROKO_FRESH_PROFILE':str(profile.resolve()),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
    server=pathlib.Path(__file__).resolve().parents[1]/'durable_server.py'
    packets=requests();returncodes={}
    for name,batch in [('',packets),('restart-',[packets[7],packets[5],packets[6],packets[8]])]:
        data=''.join(json.dumps(x)+'\n' for x in batch);(root/(name+'requests.jsonl')).write_text(data)
        with (root/(name+'stdout.txt')).open('wb') as out,(root/(name+'stderr.txt')).open('wb') as err:
            proc=subprocess.run([sys.executable,'-B',str(server)],input=data.encode(),stdout=out,stderr=err,env=env,timeout=600)
        returncodes[name or 'initial']=proc.returncode
        save(root/('after.json' if not name else 'restart-after.json'),read_state(root/'history.sqlite'))
        if proc.returncode:break
    save(root/'returncodes.json',returncodes);save(root/'source-after.json',read_state(source))

def audit(root):
    load=lambda n:json.loads((root/n).read_text())
    before,after,restarted=map(load,('before.json','after.json','restart-after.json'))
    r,t=outputs(root,''),outputs(root,'restart-');n,nt=receipt(root,''),receipt(root,'restart-')
    original=requests();captured=[json.loads(x) for x in (root/'requests.jsonl').read_text().splitlines()]
    checks=dict(request_contract=captured==original,protocol=load('returncodes.json')=={'initial':0,'restart-':0} and len(r)==10 and len(t)==4,
        default_context_refused=r[0].get('code')=='context_limit',default_failure_preserves_history=r[1]['history']==before['history'] and r[1]['revision']==6 and r[1]['pending'] is None,
        optin_seven_committed=r[2].get('status')=='completed' and r[2].get('revision')==7,
        loss_visible=all(x.get('model_context',{}).get('model_context_complete') is False and x['model_context']['authoritative_history_changed'] is False for x in (r[2],r[5])),
        default_policy_not_sticky=r[3].get('code')=='context_limit',second_failure_preserves_history=r[4]['revision']==7 and len(r[4]['history'])==14 and r[4]['pending'] is None,
        optin_eight_committed=r[5].get('status')=='completed' and r[5].get('revision')==8,
        capacity_visible=r[6].get('history_admits_turn') is False and r[6]['remaining_exchanges']==0 and r[6]['max_history_messages']==16,
        ninth_refused=r[7].get('code')=='history_limit',complete_sixteen_messages=r[8]['revision']==8 and len(r[8]['history'])==16 and r[8]['history']==after['history'],
        original_prefix_preserved=after['history'][:12]==before['history'],new_pairs_bound=after['history'][12:]==[dict(role='user',content=original[2]['text']),dict(role='assistant',content=r[2]['text']),dict(role='user',content=original[5]['text']),dict(role='assistant',content=r[5]['text'])],projection_history_bound=r[2]['model_context']['full_history_sha256']==digest(before['history']) and r[5]['model_context']['full_history_sha256']==digest(after['history'][:14]),ledger_preserved=after['cognitive_history']==before['cognitive_history'],no_pending=after['pending'] is None,
        exact_replay=r[9]==r[5],two_native_generations=sum(x['returncode']==0 and 'generation' in x for x in n['native_calls'])==2,
        two_context_rejections_no_output=sum(x['returncode']==2 and x['stdout_bytes']==0 and 'generation' not in x for x in n['native_calls'])==2,
        recall=all(all(word in x['text'].lower() for word in ('fox','robin')) for x in (r[2],r[5])),
        generation_token_counts=all(x['generation']['input_tokens']==x['model_context']['token_count']<=512 for x in (r[2],r[5])),
        native_retrieval_evidence=len(n['mork_receipts'])==4 and len(n['ecan_receipts'])==2 and n['cognitive_receipts']==[],native_success_bound=[x['generation'] for x in n['native_calls'] if x['returncode']==0 and 'generation' in x]==[r[2]['generation'],r[5]['generation']],no_autonomous_actions=all(x.get('executed_actions',0)==0 for x in r+t),
        failed_id_terminal=t[0].get('code')=='failed',restart_exact_replay=t[1]==r[5],restart_capacity=t[2]['remaining_exchanges']==0 and not t[2]['history_admits_turn'],
        restart_snapshot_unchanged=t[3]==r[8] and restarted==after,
        restart_zero_native_work=all(nt[k]==[] for k in ('native_calls','mork_receipts','cognitive_receipts','ecan_receipts','token_counter_calls')),
        source_checkpoint_unchanged=load('source-after.json')==before)
    return dict(passed=all(checks.values()),checks=checks,evidence_provenance='local validated native runtime; six exchanges resumed for two new generations; no GUI or independent reproduction',
        authoritative_exchanges=8,authoritative_messages=16,unlimited_conversation=False,
        native_attempts=len(n['native_calls']),successful_generations=sum(x['returncode']==0 and 'generation' in x for x in n['native_calls']),
        input_tokens=[x['generation']['input_tokens'] for x in (r[2],r[5])],executed_actions=0)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--profile',type=pathlib.Path);p.add_argument('--source-db',type=pathlib.Path);p.add_argument('--audit-only',action='store_true');a=p.parse_args()
    if not a.audit_only:
        if not a.profile or not a.source_db:p.error('--profile and --source-db required unless --audit-only')
        run(a.output.resolve(),a.profile,a.source_db)
    result=audit(a.output.resolve());save(a.output/('audit-result.json' if a.audit_only else 'result.json'),result);print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
