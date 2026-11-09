"""Bounded source-only acquisition; no downloaded code execution or payload extraction."""
import hashlib,json,pathlib,shutil,subprocess,urllib.request,time
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent;S=R/'build-src/cosmic-files-portals-stage'
load=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as s:
  while b:=s.read(1048576):h.update(b)
 return h.hexdigest()
def pars(text):
 for b in text.split('\n\n'):
  d={};k=None
  for l in b.splitlines():
   if l.startswith((' ','\t')) and k:d[k]+='\n'+l[1:]
   elif ':' in l:k,v=l.split(':',1);d[k]=v.strip()
  if d:yield d
plan=load(O/'missing-native-sources.json');assert len(plan)==55 and sum(f['bytes'] for f in plan)==21466411
cap=25*1024**2;reserve=4*1024**3
assert shutil.disk_usage(R).free>reserve+sum(f['bytes'] for f in plan)
checks=[];sources={};bins={}
for repo,suite,short in [('debian','trixie','debian'),('debian-security','trixie-security','security')]:
 ip=R/f'boot/tooling/lists/snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_InRelease';out=O/f'{short}-Release.verified'
 if out.exists():out.unlink()
 r=subprocess.run(['sqv','--keyring','/usr/share/keyrings/debian-archive-keyring.gpg','--output',str(out),'--cleartext',str(ip)],capture_output=True,text=True);assert r.returncode==0,r.stderr
 checks.append({'kind':'signature','path':str(ip.relative_to(R)),'sha256':sha(ip),'stdout':r.stdout,'stderr':r.stderr})
 expected={x.split()[2]:x.split()[:2] for x in out.read_text().split('SHA256:\n')[1].split('\nSHA512:')[0].splitlines() if len(x.split())==3}
 for kind,rel in [('Packages','main/binary-amd64/Packages'),('Sources','main/source/Sources')]:
  p=R/f'boot/tooling/lists/snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_{rel.replace("/","_")}';assert sha(p)==expected[rel][0] and p.stat().st_size==int(expected[rel][1]);checks.append({'kind':'index','path':str(p.relative_to(R)),'sha256':sha(p)})
  for d in pars(p.read_text()):(sources if kind=='Sources' else bins)[repo,d['Package'],d['Version']]=d
inv=load(O/'inventory.json');allfiles={};archivechecks=[]
for p in inv['runtime_owner_packages']:
 repo='debian-security' if '/debian-security/' in p['url'] else 'debian';b=bins[repo,p['package'],p['version']];s=sources[repo,p['source'],p['source_version']];assert b['SHA256']==p['sha256'] and int(b['Size'])==p['bytes']
 expected={fn:(h,int(z)) for h,z,fn in (x.split() for x in s['Checksums-Sha256'].strip().splitlines())}
 for f in p['corresponding_source_files']:
  assert expected[f['filename']]==(f['sha256'],f['bytes']);assert f['url'].endswith('/'+s['Directory']+'/'+f['filename']);allfiles[f['sha256']]=f
 if p['package'] in inv['archive_control_only_packages']:
  a=S/'apt/archives'/pathlib.Path(p['filename']).name;assert a.stat().st_size==p['bytes'] and sha(a)==p['sha256'];archivechecks.append({'package':p['package'],'sha256':p['sha256'],'bytes':p['bytes'],'method':'Whole archive hash verified against signed Packages; prior control md5sums ownership authenticated, payload bytes not independently compared.'})
for f in plan:assert allfiles[f['sha256']]==f
(O/'authentication.json').write_text(json.dumps({'checks':checks,'runtime_package_mappings_verified':len(inv['runtime_owner_packages']),'new_runtime_archives_verified':archivechecks,'payload_extraction':False},indent=2)+'\n')
D=O/'native-sources';D.mkdir(exist_ok=True);ledger=O/'incremental-download-ledger.json';state=load(ledger) if ledger.exists() else {'received_bytes':0,'cap_bytes':cap,'original_conservative_bound_unchanged':1059760437,'attempts':[]}
results=[];errors=[]
for f in plan:
 p=D/f['filename'];assert p.name==f['filename']
 if not(p.exists() and p.stat().st_size==f['bytes'] and sha(p)==f['sha256']):
  assert state['received_bytes']+f['bytes']<=cap
  assert shutil.disk_usage(R).free>reserve+f['bytes']
  attempt={'filename':f['filename'],'received_bytes':0};state['attempts'].append(attempt);ledger.write_text(json.dumps(state,indent=2)+'\n')
  try:
   assert f['url'].startswith('https://snapshot.debian.org/archive/')
   partial=p.with_name(p.name+'.partial')
   with urllib.request.urlopen(f['url'],timeout=90) as src,partial.open('wb') as dst:
    while True:
     allowed=min(65536,cap-state['received_bytes']);assert allowed>0
     chunk=src.read(allowed)
     if not chunk:break
     state['received_bytes']+=len(chunk);attempt['received_bytes']+=len(chunk);ledger.write_text(json.dumps(state,indent=2)+'\n');assert attempt['received_bytes']<=f['bytes'];assert shutil.disk_usage(R).free>reserve+len(chunk);dst.write(chunk)
   assert partial.stat().st_size==f['bytes'] and sha(partial)==f['sha256'];partial.replace(p);attempt['verified']=True
  except Exception as e:
   attempt['error']=repr(e);errors.append(attempt.copy())
  ledger.write_text(json.dumps(state,indent=2)+'\n')
 if p.exists() and sha(p)==f['sha256']:results.append(dict(f,path=str(p.relative_to(R)),verified=True))
 (O/'acquired-sources.json').write_text(json.dumps({'files':results,'errors':errors,'complete':len(results)==len(plan),'incremental_received_bytes':state['received_bytes'],'incremental_cap_bytes':cap,'remaining_incremental_bytes':cap-state['received_bytes'],'free_disk_bytes':shutil.disk_usage(R).free,'original_conservative_bound_unchanged':1059760437,'scope':'Exact official source archives only, no extraction, execution or legal-compliance claim.'},indent=2)+'\n')
 print(len(results),f['filename'],flush=True)
print('DONE',len(results),state['received_bytes'],errors)
