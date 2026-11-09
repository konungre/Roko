#!/usr/bin/env python3
"""Explicit native v2 NARS/ECAN/MORK/Granite qualification, never a unit test.

Creates synthetic history in a new directory. Runtime paths come only from the
trusted profile. The parent must run this after preparing a matching admission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

SOURCE=Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(SOURCE.parents[1]))
from cognition import extract
from recovered import render,system_message
from components.nars_hyperon.source.contract import canonical,response_from_rows

FIRST='A robin is a bird. A bird is an animal. What follows?'
FOLLOWUP='What creature did I mention, and what two kinds does it belong to?'
CANCEL='A cat is a mammal. A mammal is an animal. What follows?'


def group_rows(group):
    result=[]
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields=path.read_text().rsplit(')',1)[1].split()
            if int(fields[2])!=group or fields[0]=='Z':continue
            rss=next((int(line.split()[1])*1024 for line in (path.parent/'status').read_text().splitlines()
                      if line.startswith('VmRSS:')),0)
            result.append({'pid':int(path.parent.name),'rss':rss,'cpu_ticks':int(fields[11])+int(fields[12]),
                           'comm':(path.parent/'comm').read_text().strip()})
        except (OSError,ValueError):pass
    return result


def read_state(database,session):
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT revision,history,cognitive_history,pending FROM sessions WHERE id=?',(session,)).fetchone()
    if row is None:return {'revision':0,'history':[],'cognitive_history':[],'pending':None}
    return dict(revision=row[0],history=json.loads(row[1]),cognitive_history=json.loads(row[2]),pending=row[3])


def good_mork(receipt,revision,messages):
    native=receipt.get('native',{})
    return (receipt.get('implementation')=='native-mork-v2-complete-transcript-index'
            and receipt.get('revision')==revision and receipt.get('indexed_messages')==messages
            and receipt.get('history_omitted') is False and receipt.get('authorizes_actions') is False
            and native.get('implementation')=='native-mork-rebuild-bounded-facts'
            and native.get('descendants_cleaned') is True)


def prompt_hash(history,text,context,cognition):
    system=system_message(SimpleNamespace(context=context,cognitive_context=cognition))
    prompt=render([{'role':'system','content':system}]+history+[{'role':'user','content':text}])
    return hashlib.sha256(prompt.encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    profile=json.loads(args.profile.read_text())
    required={'nars_cognition','mork_memory','ecan'}
    if not required<=set(profile):raise ValueError('Combined NARS, MORK and ECAN profile required')
    database=args.output/'state/history.sqlite'
    env={**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve()),'ROKO_HISTORY_DB':str(database),
         'PYTHONDONTWRITEBYTECODE':'1'}
    command=[sys.executable,'-B',str(SOURCE/'durable_server.py')]
    checks={};phases=[];failure=None;cancel_receipt=None;started=time.monotonic()
    def check(name,condition):checks[name]=bool(condition)
    def run(name,requests):
        folder=args.output/name;folder.mkdir()
        (folder/'requests.json').write_bytes(canonical(requests)+b'\n')
        with (folder/'stderr.txt').open('xb') as err:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=env)
            try:out,_=process.communicate(b'\n'.join(canonical(r) for r in requests)+b'\n',timeout=420)
            except BaseException:
                process.terminate()
                try:out,_=process.communicate(timeout=10)
                except subprocess.TimeoutExpired:process.kill();out,_=process.communicate(timeout=3)
                (folder/'stdout.txt').write_bytes(out);raise
        (folder/'stdout.txt').write_bytes(out)
        replies=[json.loads(line) for line in out.decode().splitlines()]
        records=[json.loads(line.split(' ',1)[1]) for line in (folder/'stderr.txt').read_text().splitlines()
                 if line.startswith('ROKO_FRESH_CONVERSATION ')]
        if process.returncode or len(replies)!=len(requests) or len(records)!=1:
            raise RuntimeError('Protocol/native finalization failed in '+name)
        record=records[0]
        info={'phase':name,'returncode':process.returncode,'replies':replies,
              **{key:len(record[key]) for key in ('native_calls','ecan_receipts','mork_receipts','cognitive_receipts')}}
        phases.append(info);(args.output/'progress.json').write_bytes(canonical(phases)+b'\n')
        print(json.dumps(info),flush=True)
        for call in record['native_calls']:
            if call['returncode']==0:
                check(name+'_model_verification',call.get('model_verified_before_history_commit') is True
                      and 'descendants_cleaned=1' in call['stderr'])
        return replies,info,record
    def turn(rid,rev,text,context=None,limit=128,session='main'):
        return dict(api_version=2,op='turn',session_id=session,request_id=rid,expected_revision=rev,
                    text=text,context=context or [],max_output_tokens=limit)
    def snapshot(session='main'):return dict(api_version=2,op='snapshot',session_id=session)
    context=[dict(id=name,text=text,sti=sti,lti=10,stimulus=0) for name,text,sti in
             [('brief','Brief.',100),('exact','Exact terms.',80),('safe','No actions.',60),
              ('uncertain','Advisory.',40),('unused','Rain.',1)]]
    try:
        first=turn('first',0,FIRST,context)
        replies,info,record=run('01-combined',[first]);one=replies[0]
        check('first_completed',one.get('status')=='completed' and one.get('revision')==1)
        check('first_native_components',info['native_calls']==1 and info['ecan_receipts']==1
              and info['mork_receipts']==1 and info['cognitive_receipts']==1)
        check('first_ecan_selection',one.get('context_ids')==['brief','exact','safe','uncertain'])
        check('first_mork',good_mork(record['mork_receipts'][0],0,0))
        cognitive=record['cognitive_receipts'][0];native=cognitive['receipt'];packet=json.loads(native['stdout'])
        check('first_actual_nars',native['status']=='passed' and native['returncode']==0
              and response_from_rows(cognitive['request'],packet['native_rows'])==cognitive['response'])
        check('first_nars_snapshot',cognitive['snapshot_sha256']==hashlib.sha256(canonical({'text':FIRST,'history':[]})).hexdigest())
        ledger=[cognitive['prompt_context']]
        selected=[{'id':x['id'],'text':x['text']} for x in context[:4]]
        check('first_prompt_binding',record['native_calls'][0]['prompt_sha256']==prompt_hash([],FIRST,selected,ledger))
        committed=read_state(database,'main')
        check('ledger_atomic_commit',committed['revision']==1 and len(committed['history'])==2
              and committed['cognitive_history']==ledger and committed['pending'] is None)
        if not checks['first_completed']:raise RuntimeError('First turn did not commit')
        second=turn('second',1,FOLLOWUP)
        replies,info,record=run('02-restart-replay-cas',[snapshot(),first,turn('stale',0,FIRST),second,snapshot()])
        check('restart_history',replies[0]['revision']==1 and replies[0]['history']==committed['history'])
        check('saved_replay',replies[1]==one and info['native_calls']==1)
        check('stale_cas',replies[2].get('code')=='stale_revision')
        check('followup_no_nars_rerun',info['cognitive_receipts']==0 and info['ecan_receipts']==0)
        check('followup_mork',info['mork_receipts']==1 and good_mork(record['mork_receipts'][0],1,2))
        check('followup_prompt_binding',record['native_calls'][0]['prompt_sha256']==prompt_hash(committed['history'],FOLLOWUP,[],ledger))
        check('followup_recall',replies[3].get('status')=='completed' and replies[3].get('revision')==2
              and all(re.search(r'\b'+term+r'\b',replies[3].get('text',''),re.I) for term in ('robin','bird','animal')))
        baseline=read_state(database,'main')
        check('durable_ledger_restored',baseline['cognitive_history']==ledger and len(baseline['history'])==4)
        if baseline['revision']!=2:raise RuntimeError('Followup did not commit')
        partial=turn('partial',0,'Write a long detailed story about a lighthouse keeper.',limit=4,session='limits')
        replies,info,record=run('03-output-limit',[partial]);short=replies[0]
        check('explicit_truncation',short.get('status')=='truncated' and short.get('generation',{}).get('finish_reason')=='length'
              and short.get('generation',{}).get('output_tokens')==4 and short.get('revision')==1)
        replies,info,record=run('04-partial-replay',[partial,snapshot('limits')])
        check('partial_replay_no_native',replies[0]==short and all(info[x]==0 for x in
              ('native_calls','cognitive_receipts','ecan_receipts','mork_receipts')))
        replies,info,record=run('05-input-limit',[turn('overflow',0,'a b c d '*480,session='overflow'),snapshot('overflow')])
        check('context_rejected_without_commit',replies[0].get('code')=='context_limit'
              and replies[1]['revision']==0 and replies[1]['history']==[] and replies[1]['pending'] is None)
        check('overflow_no_cognitive_ledger',read_state(database,'overflow')['cognitive_history']==[])
        cancelled=turn('cancelled',2,CANCEL)
        evidence_root=Path(profile['nars_cognition']['evidence_root'])
        old_evidence=set(evidence_root.rglob('receipt.json'))
        folder=args.output/'06-cancel';folder.mkdir();(folder/'request.json').write_bytes(canonical(cancelled)+b'\n')
        with (folder/'stdout.txt').open('xb') as out,(folder/'stderr.txt').open('xb') as err:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
            try:
                process.stdin.write(canonical(cancelled)+b'\n');process.stdin.flush()
                deadline=time.monotonic()+120;supervisor=None;before=[]
                while time.monotonic()<deadline and process.poll() is None:
                    for line in (folder/'stderr.txt').read_text().splitlines():
                        if line.startswith('ROKO_NATIVE_STARTED '):supervisor=json.loads(line.split(' ',1)[1])['supervisor_pid']
                    before=group_rows(supervisor) if supervisor else []
                    if any(r['comm']=='infer' and r['rss']>3*1024**3 and r['cpu_ticks']>50 for r in before):break
                    time.sleep(.1)
            finally:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                if process.stdin:process.stdin.close()
        deadline=time.monotonic()+10
        while supervisor and group_rows(supervisor) and time.monotonic()<deadline:time.sleep(.05)
        after=group_rows(supervisor) if supervisor else []
        expected=extract(CANCEL,3);nars_evidence=[]
        for path in set(evidence_root.rglob('receipt.json'))-old_evidence:
            receipt=json.loads(path.read_text())
            if receipt.get('request_sha256')==hashlib.sha256(canonical(expected)).hexdigest():
                nars_evidence.append({'path':str(path),'receipt':receipt})
        cancel_receipt={'before':before,'after':after,'returncode':process.returncode,
                        'answer_bytes':(folder/'stdout.txt').stat().st_size,'nars_evidence':nars_evidence}
        (folder/'result.json').write_bytes(canonical(cancel_receipt)+b'\n')
        check('cancel_resident_model_cleanup',any(r['comm']=='infer' and r['rss']>3*1024**3 and r['cpu_ticks']>50 for r in before)
              and not after and cancel_receipt['answer_bytes']==0)
        check('cancel_nars_completed_before_model',len(nars_evidence)==1 and nars_evidence[0]['receipt']['status']=='passed')
        pending=read_state(database,'main')
        check('cancel_no_ledger_commit',pending['revision']==2 and pending['history']==baseline['history']
              and pending['cognitive_history']==ledger and pending['pending']=='cancelled')
        recover=dict(api_version=2,op='recover',session_id='main',request_id='cancelled',expected_revision=2)
        replies,info,record=run('07-explicit-recovery',[snapshot(),cancelled,recover,snapshot(),first])
        check('pending_not_reexecuted',replies[1].get('code')=='pending' and all(info[x]==0 for x in
              ('native_calls','cognitive_receipts','ecan_receipts','mork_receipts')))
        check('explicit_recovery',replies[2].get('status')=='interrupted' and replies[3]['revision']==2
              and replies[3]['pending'] is None and replies[4]==one)
        final=read_state(database,'main')
        check('recovery_preserves_ledger',final==baseline)
    except BaseException as error:
        failure=repr(error)
    result={'status':'passed' if failure is None and checks and all(checks.values()) else 'failed',
            'checks':checks,'phases':phases,'cancellation':cancel_receipt,'error':failure,
            'seconds':round(time.monotonic()-started,3),'profile_sha256':hashlib.sha256(args.profile.read_bytes()).hexdigest(),
            'executed_actions':0,'full_nars':False,'full_autonomous_omega':False,'graphical_ui_tested':False}
    (args.output/'result.json').write_bytes(canonical(result)+b'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'error':failure,'seconds':result['seconds']},indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
