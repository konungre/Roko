#!/usr/bin/env python3
"""Pin authorized cached Debian solver transaction, optionally download/extract only."""
import argparse,concurrent.futures,hashlib,json,pathlib,re,shutil,subprocess,urllib.request
STAGE=pathlib.Path(__file__).resolve().parent;ROOT=STAGE.parents[1];LISTS=ROOT/'boot/tooling/lists'
def sha(data):return hashlib.sha256(data).hexdigest()
def paragraphs(text):
 for block in text.split('\n\n'):
  d={};key=None
  for line in block.splitlines():
   if line.startswith((' ','\t')) and key:d[key]+='\n'+line[1:]
   elif ':' in line:key,value=line.split(':',1);d[key]=value.lstrip()
  if d:yield d

def make_lock():
 records=[];source_records={};metadata=[]
 for repo,suite,release in [('debian','trixie','debian'),('debian-security','trixie-security','security')]:
  verified=STAGE/f'apt/{release}-Release.verified';text=verified.read_text();section=text.split('SHA256:\n',1)[1].split('\nSHA512:',1)[0];hashes={}
  for line in section.splitlines():
   fields=line.split()
   if len(fields)==3 and len(fields[0])==64:hashes[fields[2]]=(fields[0],int(fields[1]))
  for kind,rel in [('Packages','main/binary-amd64/Packages'),('Sources','main/source/Sources')]:
   name=f'snapshot.debian.org_archive_{repo}_20261103T013555Z_dists_{suite}_{rel.replace("/","_")}';path=LISTS/name;data=path.read_bytes();expected,size=hashes[rel]
   if sha(data)!=expected or len(data)!=size:raise ValueError('Signed index checksum mismatch: '+name)
   metadata.append({'file':str(path.relative_to(ROOT)),'sha256':expected,'bytes':size,'verified_release':str(verified.relative_to(STAGE))})
   for d in paragraphs(data.decode()):
    d['_repository']=repo
    if kind=='Packages':records.append(d)
    else:source_records[(d['Package'],d['Version'],repo)]=d
 transaction=re.findall(r'^Inst (\S+) \((\S+)',(STAGE/'logs/apt-solver.txt').read_text(),re.M);pkgs=[]
 for name,version in transaction:
  name=name.removesuffix(':amd64');matches=[d for d in records if d['Package']==name and d['Version']==version and d['Architecture'] in ['amd64','all']]
  if not matches:raise ValueError('No exact signed metadata: '+name+' '+version)
  if len({d['SHA256'] for d in matches})!=1:raise ValueError('Ambiguous archive: '+name)
  d=matches[0];source=d.get('Source',name);m=re.fullmatch(r'([^ ]+)(?: \(([^)]+)\))?',source);sn,sv=m[1],m[2] or version
  src=source_records.get((sn,sv,d['_repository']))
  if not src:raise ValueError('Source metadata absent: '+sn+' '+sv)
  srcfiles=[]
  for line in src['Checksums-Sha256'].strip().splitlines():
   h,n,fn=line.split();srcfiles.append({'filename':fn,'bytes':int(n),'sha256':h,'url':f"https://snapshot.debian.org/archive/{d['_repository']}/20261103T013555Z/{src['Directory']}/{fn}"})
  pkgs.append({'package':name,'version':version,'architecture':d['Architecture'],'sha256':d['SHA256'],'bytes':int(d['Size']),'filename':d['Filename'],'url':f"https://snapshot.debian.org/archive/{d['_repository']}/20261103T013555Z/{d['Filename']}",'depends':d.get('Depends',''),'pre_depends':d.get('Pre-Depends',''),'source':sn,'source_version':sv,'corresponding_source_files':srcfiles})
 result={'schema':1,'snapshot':'20261103T013555Z','signature_verification':'sqv against existing Debian archive keyring; logs/debian-signature.txt and logs/security-signature.txt','metadata':metadata,'solver_transaction_sha256':sha((STAGE/'logs/apt-solver.txt').read_bytes()),'seeds':(STAGE/'apt/seeds.txt').read_text().splitlines(),'package_count':len(pkgs),'archive_bytes':sum(p['bytes'] for p in pkgs),'packages':pkgs,'scope':'Workspace extraction only, empty dpkg status, no recommends, no maintainer scripts; includes build and runtime closure. Corresponding source archives indexed but not downloaded.'};(STAGE/'debian-packages.lock.json').write_text(json.dumps(result,indent=2)+'\n');return result

def acquire(p):
 target=STAGE/'apt/archives'/pathlib.Path(p['filename']).name;reused=False
 if not target.exists():
  # Reuse only archives whose bytes match signed metadata, irrespective of name.
  old=json.loads((ROOT/'boot/tooling-packages.lock.json').read_text())['packages']
  candidates=[ROOT/x['file'] for x in old if x['sha256']==p['sha256']]
  candidates += [ROOT/'build-src'/name/'apt/archives'/pathlib.Path(p['filename']).name for name in ['cosmic-comp-stage','cosmic-desktop-stage','basilisk-stage','basilisk-layer-stage']]
  for path in candidates:
   if path.is_file() and sha(path.read_bytes())==p['sha256']:shutil.copyfile(path,target);reused=True;break
  else:
   tmp=target.with_suffix('.partial')
   with urllib.request.urlopen(p['url'],timeout=120) as source,tmp.open('wb') as out:shutil.copyfileobj(source,out)
   if sha(tmp.read_bytes())!=p['sha256'] or tmp.stat().st_size!=p['bytes']:raise ValueError('Archive mismatch: '+p['package'])
   tmp.replace(target)
 if sha(target.read_bytes())!=p['sha256'] or target.stat().st_size!=p['bytes']:raise ValueError('Archive mismatch: '+p['package'])
 return target,reused

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--download-extract',action='store_true');args=parser.parse_args();lock=make_lock();print('Pinned',len(lock['packages']),'packages;',lock['archive_bytes'],'archive bytes',flush=True)
 if args.download_extract:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   files=list(pool.map(acquire,lock['packages']))
  target=STAGE/'sysroot';target.mkdir(exist_ok=True)
  for path,_ in files:subprocess.run(['dpkg-deb','-x',str(path),str(target)],check=True,timeout=120)
  receipts=[]
  for path in sorted(target.rglob('*')):
   if path.is_symlink():receipts.append({'path':str(path.relative_to(target)),'target':str(path.readlink()),'kind':'symlink'})
   elif path.is_file():receipts.append({'path':str(path.relative_to(target)),'sha256':sha(path.read_bytes()),'kind':'file','mode':path.stat().st_mode & 0o7777})
  (STAGE/'debian-files.lock.json').write_text(json.dumps({'files':receipts},indent=2)+'\n')
  print('Extracted',len(files),'archives;',sum(x[1] for x in files),'reused;',len(receipts),'files/symlinks; no maintainer scripts',flush=True)
if __name__=='__main__':main()
