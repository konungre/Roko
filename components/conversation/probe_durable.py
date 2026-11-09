#!/usr/bin/env python3
"""Actual native v2 qualification across restarts, CAS, limits and cancellation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parent
    env={**os.environ,'ROKO_FRESH_PROFILE':str(args.profile.resolve()),
         'ROKO_HISTORY_DB':str((args.output/'state/history.sqlite').resolve())}
    command=[sys.executable,'-B',str(source/'durable_server.py')]
    checks={}; phases=[]
    def run(name,requests):
        folder=args.output/name;folder.mkdir()
        (folder/'requests.json').write_text(json.dumps(requests,indent=2)+'\n')
        with (folder/'stderr.txt').open('wb') as err:
            p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=env)
            try:out,_=p.communicate(('\n'.join(json.dumps(x) for x in requests)+'\n').encode(),timeout=420)
            except BaseException:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait()
                raise
        (folder/'stdout.txt').write_bytes(out)
        replies=[json.loads(x) for x in out.decode().splitlines()]
        native=[json.loads(x.split(' ',1)[1]) for x in (folder/'stderr.txt').read_text().splitlines()
                if x.startswith('ROKO_FRESH_CONVERSATION ')]
        info={'name':name,'returncode':p.returncode,'replies':replies,
              'native_calls':len(native[0]['native_calls']) if len(native)==1 else None,
              'ecan_calls':len(native[0]['ecan_receipts']) if len(native)==1 else None}
        phases.append(info)
        (args.output/'progress.json').write_text(json.dumps(phases,indent=2)+'\n')
        if p.returncode or len(replies)!=len(requests):raise RuntimeError('Protocol failure in '+name)
        print(name+': '+json.dumps(info),flush=True)
        return replies,info
    def turn(rid,rev,text,context=None,limit=128,session='main'):
        return dict(api_version=2,op='turn',session_id=session,request_id=rid,
                    expected_revision=rev,text=text,context=context or [],max_output_tokens=limit)
    def snapshot(session='main'):return dict(api_version=2,op='snapshot',session_id=session)
    context=[dict(id=name,text=text,sti=sti,lti=10,stimulus=0) for name,text,sti in [
        ('setting','The story is set in a lighthouse.',100),('style','Use a calm tone.',80),
        ('character','The keeper is named Mara.',60),('length','Be concise.',40),
        ('unrelated','Shopping list: buy detergent.',1)]]
    first=turn('first',0,'Suggest one short opening sentence using the setting from context.',context)
    replies,info=run('01-ecan',[first]);one=replies[0]
    checks['native_ecan_and_granite']=info['native_calls']==1 and info['ecan_calls']==1
    checks['selected_context']=one.get('context_ids')==['setting','style','character','length']
    checks['first_complete']=one.get('status')=='completed' and one.get('revision')==1 and 'lighthouse' in one.get('text','').lower()
    second=turn('second',1,'What setting did we use? Answer in one short sentence.')
    replies,info=run('02-restart-replay-cas',[snapshot(),first,turn('stale',0,'This must not run.'),second,snapshot()])
    checks['durable_restart']=replies[0]['revision']==1 and len(replies[0]['history'])==2
    checks['exact_replay']=replies[1]==one and info['native_calls']==1
    checks['stale_cas']=replies[2].get('code')=='stale_revision'
    checks['recall']=replies[3].get('revision')==2 and 'lighthouse' in replies[3].get('text','').lower()
    partial=turn('partial',2,'Write a long detailed story about the lighthouse keeper.',limit=4)
    replies,info=run('03-output-limit',[partial,snapshot()]);short=replies[0]
    checks['explicit_output_limit']=short.get('status')=='truncated' and short['generation']['finish_reason']=='length' and short['generation']['output_tokens']==4 and short['revision']==3
    replies,info=run('04-partial-replay',[partial,snapshot()])
    checks['partial_replay']=replies[0]==short and info['native_calls']==0 and replies[1]['revision']==3
    replies,info=run('05-context-limit',[turn('too-long',0,'a b c d '*480,session='overflow'),snapshot('overflow')])
    checks['context_limit_no_commit']=replies[0].get('code')=='context_limit' and replies[1]['revision']==0 and replies[1]['history']==[] and replies[1]['pending'] is None
    def group(pid):
        rows=[]
        for p in Path('/proc').glob('[0-9]*/stat'):
            try:
                fields=p.read_text().rsplit(')',1)[1].split()
                if int(fields[2])==pid and fields[0]!='Z':rows.append(int(p.parent.name))
            except (OSError,ValueError):pass
        return rows
    cancelled=turn('cancelled',3,'Write another sentence about the keeper.')
    folder=args.output/'06-cancel';folder.mkdir()
    with (folder/'stdout.txt').open('wb') as out,(folder/'stderr.txt').open('wb') as err:
        p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
        p.stdin.write((json.dumps(cancelled)+'\n').encode());p.stdin.flush()
        deadline=time.monotonic()+90;supervisor=None
        while time.monotonic()<deadline and p.poll() is None:
            for line in (folder/'stderr.txt').read_text().splitlines():
                if line.startswith('ROKO_NATIVE_STARTED '):supervisor=json.loads(line.split(' ',1)[1])['supervisor_pid']
            if supervisor and len(group(supervisor))>=2:break
            time.sleep(.1)
        before=group(supervisor) if supervisor else []
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        p.stdin.close();deadline=time.monotonic()+10
        while supervisor and group(supervisor) and time.monotonic()<deadline:time.sleep(.05)
        after=group(supervisor) if supervisor else []
    cancel_receipt={'before':before,'after':after,'returncode':p.returncode,'answer_bytes':(folder/'stdout.txt').stat().st_size}
    (folder/'result.json').write_text(json.dumps(cancel_receipt,indent=2)+'\n')
    checks['cancel_cleanup']=len(before)>=2 and not after and cancel_receipt['answer_bytes']==0
    recover=dict(api_version=2,op='recover',session_id='main',request_id='cancelled',expected_revision=3)
    replies,info=run('07-explicit-recovery',[snapshot(),cancelled,recover,snapshot(),partial])
    checks['pending_no_replay']=replies[0]['revision']==3 and replies[0]['pending']=='cancelled' and replies[1].get('code')=='pending' and info['native_calls']==0
    checks['explicit_recovery']=replies[2].get('status')=='interrupted' and replies[3]['pending'] is None and replies[3]['revision']==3 and len(replies[3]['history'])==6 and replies[4]==short
    result={'passed':all(checks.values()),'checks':checks,'phases':phases,'cancel':cancel_receipt,
            'executed_actions':0,'graphical_ui_tested':False,'full_autonomous_omega':False}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
