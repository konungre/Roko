#!/usr/bin/env python3
"""Install exact official upstream toolchain in this stage; no global changes."""
import concurrent.futures,hashlib,json,pathlib,shutil,subprocess,tarfile,urllib.request
S=pathlib.Path(__file__).resolve().parent;D=S/'toolchain-downloads';M=json.loads((D/'artifacts.json').read_text());prefix=S/'rust-1.93.0';unpack=S/'toolchain-unpacked';unpack.mkdir(exist_ok=True)
def obtain(p):
 url=p['url'];assert url.startswith('https://static.rust-lang.org/dist/2026-01-22/');path=D/url.rsplit('/',1)[1]
 if not path.exists():
  tmp=path.with_suffix('.partial')
  with urllib.request.urlopen(url,timeout=120) as source,tmp.open('wb') as sink:shutil.copyfileobj(source,sink)
  if hashlib.sha256(tmp.read_bytes()).hexdigest()!=p['sha256']:raise ValueError('Official archive hash mismatch')
  tmp.replace(path)
 if hashlib.sha256(path.read_bytes()).hexdigest()!=p['sha256']:raise ValueError('Official archive hash mismatch')
 return path
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:paths=list(pool.map(obtain,M['artifacts']))
for path in paths:
 with tarfile.open(path,'r:xz') as archive:archive.extractall(unpack,filter='data')
 directory=unpack/path.name.removesuffix('.tar.xz')
 subprocess.run(['sh','install.sh','--prefix='+str(prefix),'--disable-ldconfig'],cwd=directory,check=True,timeout=120)
receipt={'prefix':str(prefix),'source_manifest':M,'installed_files':[]}
for path in sorted(prefix.rglob('*')):
 if path.is_file() and not path.is_symlink():receipt['installed_files'].append({'path':str(path.relative_to(prefix)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
receipt['rustc_version']=subprocess.check_output([str(prefix/'bin/rustc'),'-vV'],text=True);receipt['cargo_version']=subprocess.check_output([str(prefix/'bin/cargo'),'-V'],text=True)
(S/'rust-toolchain.lock.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['rustc_version'],receipt['cargo_version'])
