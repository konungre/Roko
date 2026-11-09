"""Explicit source-copy resource failure test; normal source and source DB stay unchanged."""
import pathlib,shutil,sqlite3,json,hashlib,subprocess,sys,os
import argparse
parser=argparse.ArgumentParser(description='Actual provider resource_limit with a separately copied stricter3GiB supervisor')
parser.add_argument('--profile',required=True,type=pathlib.Path);parser.add_argument('--source-db',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
args=parser.parse_args();root=args.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
repo=pathlib.Path(__file__).resolve().parents[3];shutil.copytree(repo,root/'source',ignore=shutil.ignore_patterns('.git','__pycache__'));supervise=root/'source/components/conversation/fresh_supervise.py';s=supervise.read_text();assert s.count('rss > 5 * 1024**3')==1;supervise.write_text(s.replace('rss > 5 * 1024**3','rss > 3 * 1024**3'))
profile=json.loads(args.profile.resolve().read_text());files={}
for path,digest in profile['files'].items():
 old=pathlib.Path(path)
 if old.is_relative_to(repo):
  new=root/'source'/old.relative_to(repo);files[str(new)]=hashlib.sha256(new.read_bytes()).hexdigest()
 else:files[path]=digest
profile['files']=files;(root/'profile-low-rss.json').write_text(json.dumps(profile,indent=2)+'\n')
fixture=args.source_db.resolve()
with sqlite3.connect(fixture.as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(root/'history.sqlite') as b:a.backup(b)
def state():
 with sqlite3.connect((root/'history.sqlite').as_uri()+'?mode=ro',uri=True) as d:r=d.execute("select revision,history,cognitive_history,pending from sessions where id='language'").fetchone()
 return dict(revision=r[0],history=json.loads(r[1]),cognitive_history=json.loads(r[2]),pending=r[3])
before=state();(root/'before.json').write_text(json.dumps(before,indent=2)+'\n')
original=dict(api_version=2,op='turn',session_id='language',request_id='lowered-rss',expected_revision=6,text='Which two creatures did we discuss? Answer in one short sentence. '+'Please keep the answer brief. '*4,context=[dict(id='brief',text='Answer in one short sentence.',sti=100,lti=10,stimulus=0)],max_output_tokens=32);snapshot=dict(api_version=2,op='snapshot',session_id='language')
def endpoint(name,packets,source,config):
 data=''.join(json.dumps(x)+'\n' for x in packets);(root/(name+'-requests.jsonl')).write_text(data)
 env={**os.environ,'ROKO_FRESH_PROFILE':str(config),'ROKO_HISTORY_DB':str(root/'history.sqlite'),'PYTHONDONTWRITEBYTECODE':'1'}
 p=subprocess.run([sys.executable,'-B',str(source/'components/conversation/durable_server.py')],input=data.encode(),capture_output=True,env=env,timeout=240)
 (root/(name+'-stdout.txt')).write_bytes(p.stdout);(root/(name+'-stderr.txt')).write_bytes(p.stderr);assert p.returncode==0,p.stderr[-1000:]
 return [json.loads(x) for x in p.stdout.splitlines()],next(json.loads(x.split(' ',1)[1]) for x in p.stderr.decode().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
a,ra=endpoint('failure',[original,snapshot,original],root/'source',root/'profile-low-rss.json');middle=state();(root/'middle.json').write_text(json.dumps(middle,indent=2)+'\n')
retry={**original,'request_id':'explicit-normal-retry'};b,rb=endpoint('recovery',[original,retry,retry,snapshot],repo,args.profile.resolve());after=state();(root/'after.json').write_text(json.dumps(after,indent=2)+'\n')
checks=dict(real_resource_error=a[0].get('code')=='resource_limit',lowered_guard_proved=len(ra['native_calls'])==1 and ra['native_calls'][0].get('terminal_error')=='resource_limit' and 'ROKO_SUPERVISOR reason=native-tree-rss-cap descendants_cleaned=1' in ra['native_calls'][0]['stderr'],no_partial_generation='generation' not in ra['native_calls'][0] and ra['native_calls'][0]['stdout_bytes']==0,failed_history_unchanged=middle==before and a[1]['history']==before['history'],failed_id_terminal=a[2].get('code')=='failed' and b[0].get('code')=='failed',explicit_new_id_success=b[1].get('status')=='completed' and b[1].get('revision')==7 and 512<b[1]['generation']['input_tokens']<=768,replay_exact=b[2]==b[1],recovery_one_native_call=len(rb['native_calls'])==1 and rb['native_calls'][0]['returncode']==0,full_history_and_cognition=after['history'][:12]==before['history'] and len(after['history'])==14 and after['cognitive_history']==before['cognitive_history'],no_pending=after['pending'] is None,normal_guard_unchanged='rss > 5 * 1024**3' in (repo/'components/conversation/fresh_supervise.py').read_text())
result=dict(passed=all(checks.values()),checks=checks,provenance='Actual provider resource_limit with isolated RSS threshold tightened to3GiB; normal5GiB supervisor untouched. Explicit recovery uses a new request ID under the normal experimental profile. No production activation or deliberate host exhaustion.')
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
