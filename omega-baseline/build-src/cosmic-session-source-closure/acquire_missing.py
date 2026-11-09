"""Prepared bounded source-byte acquisition. Not executed by the session audit."""
import hashlib,json,pathlib,urllib.request,concurrent.futures
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];H=R/'build-src/cosmic-source-closure'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((O/'acquisition-plan.json').read_text());prior=630439367
assert prior+sum(f['bytes'] for f in plan)<=1024**3
used=sum(p.stat().st_size for root in [O,H] for p in root.rglob('*') if p.is_file())
assert used+sum(f['bytes'] for f in plan)<=5*1024**3
D=O/'native-sources';D.mkdir(exist_ok=True)
def fetch(f):
 p=D/f['filename'];assert pathlib.Path(f['filename']).name==f['filename'];downloaded=False
 if not (p.exists() and p.stat().st_size==f['bytes'] and sha(p)==f['sha256']):
  assert f['url'].startswith('https://snapshot.debian.org/archive/')
  partial=D/(f['filename']+'.partial');n=0
  with urllib.request.urlopen(f['url'],timeout=90) as src,partial.open('wb') as dst:
   while b:=src.read(1024*1024):
    n+=len(b);assert n<=f['bytes'];dst.write(b)
  assert n==f['bytes'] and sha(partial)==f['sha256'];partial.replace(p);downloaded=True
 assert sha(p)==f['sha256'];print(f['filename'],flush=True)
 return dict(f,local_path=str(p.relative_to(R)),verified=True,downloaded_in_this_pass=downloaded)
results=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 jobs={pool.submit(fetch,f):f for f in plan}
 for job in concurrent.futures.as_completed(jobs):
  try:results.append(job.result())
  except Exception as e:errors.append({'filename':jobs[job]['filename'],'error':str(e)})
  (O/'acquired-native-sources.json').write_text(json.dumps({'files':results,'errors':errors,'complete':len(results)==len(plan) and not errors,'source_bytes':sum(f['bytes'] for f in results),'scope':'Source-byte verification only, no extraction/install/compliance claim.'},indent=2)+'\n')
print('Verified',len(results),'errors',errors);raise SystemExit(bool(errors))
