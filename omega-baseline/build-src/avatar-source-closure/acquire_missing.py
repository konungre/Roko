"""Prepared source-only fetcher. Do not run without acquisition authorization."""
import hashlib,json,pathlib,urllib.request,concurrent.futures,threading
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((O/'acquisition-plan.json').read_text());prior_bound=869413221;cap=1024**3
assert prior_bound+sum(f['bytes'] for f in plan)<=cap
roots=[R/'build-src/cosmic-source-closure',R/'build-src/cosmic-session-source-closure',O]
assert sum(p.stat().st_size for root in roots for p in root.rglob('*') if p.is_file())+sum(f['bytes'] for f in plan)<5*1024**3
D=O/'native-sources';D.mkdir(exist_ok=True);ledger=O/'download-ledger.json';state=json.loads(ledger.read_text()) if ledger.exists() else {'received_bytes':0,'prior_conservative_bound':prior_bound}
mutex=threading.Lock()
def fetch(f):
 assert pathlib.Path(f['filename']).name==f['filename'];p=D/f['filename']
 if not (p.exists() and p.stat().st_size==f['bytes'] and sha(p)==f['sha256']):
  assert f['url'].startswith('https://snapshot.debian.org/archive/')
  partial=p.with_name(p.name+'.partial');n=0
  with urllib.request.urlopen(f['url'],timeout=90) as src,partial.open('wb') as dst:
   while b:=src.read(1024*1024):
    n+=len(b)
    with mutex:
     state['received_bytes']+=len(b);ledger.write_text(json.dumps(state,indent=2)+'\n');assert prior_bound+state['received_bytes']<=cap
    assert n<=f['bytes']
    dst.write(b)
  assert n==f['bytes'] and sha(partial)==f['sha256'];partial.replace(p)
 assert sha(p)==f['sha256'];print(f['filename'],flush=True)
 return dict(f,path=str(p.relative_to(R)),verified=True)
results=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 jobs={pool.submit(fetch,f):f for f in plan}
 for job in concurrent.futures.as_completed(jobs):
  try:results.append(job.result())
  except Exception as e:errors.append({'file':jobs[job]['filename'],'error':str(e)})
  with mutex:
   (O/'acquired-sources.json').write_text(json.dumps({'files':results,'errors':errors,'complete':len(results)==len(plan) and not errors,'download_ledger':state,'scope':'Verified source archives only; no extraction/install/compliance claim.'},indent=2)+'\n')
print('Completed',len(results),'errors',errors);raise SystemExit(bool(errors))
