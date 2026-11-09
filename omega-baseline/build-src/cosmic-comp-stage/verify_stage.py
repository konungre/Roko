#!/usr/bin/env python3
"""Read-only verification before using staged native packages and Rust sources."""
import hashlib,json,pathlib,subprocess
S=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 errors=[]
 for record in json.loads((S/'debian-files.lock.json').read_text())['files']:
  p=S/'sysroot'/record['path']
  if record['kind']=='symlink':
   if not p.is_symlink() or str(p.readlink())!=record['target']:errors.append(str(p))
  elif not p.is_file() or p.is_symlink() or sha(p)!=record['sha256'] or (p.stat().st_mode & 0o7777)!=record['mode']:errors.append(str(p))
 rust=json.loads((S/'rust-sources.lock.json').read_text())
 if sha(S/'source/Cargo.lock')!=rust['cargo_lock_sha256']:errors.append('Cargo.lock')
 if subprocess.check_output(['git','-C',str(S/'source'),'rev-parse','HEAD'],text=True).strip()!=rust['commit']:errors.append('source HEAD')
 if subprocess.run(['git','-C',str(S/'source'),'diff','--quiet','HEAD']).returncode:errors.append('source tracked modifications')
 for p in rust['packages']:
  if sha(S/p['manifest_path'])!=p['manifest_sha256']:errors.append(p['manifest_path'])
  if p.get('archive_path') and sha(S/p['archive_path'])!=p['archive_sha256']:errors.append(p['archive_path'])
 for path,record in rust['git_checkouts'].items():
  if subprocess.check_output(['git','-C',str(S/path),'rev-parse','HEAD'],text=True).strip()!=record['commit']:errors.append(path)
  if subprocess.run(['git','-C',str(S/path),'diff','--quiet','HEAD']).returncode:errors.append(path+' tracked modifications')
 return {'success':not errors,'errors':errors,'rust_packages':rust['package_count'],'scope':'Observed file/archive integrity and pinned Git revisions; not a security or licensing audit.'}
if __name__=='__main__':
 r=verify();print(json.dumps(r,indent=2));raise SystemExit(not r['success'])
