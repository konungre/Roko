#!/usr/bin/env python3
import hashlib,json,pathlib
S=pathlib.Path(__file__).resolve().parent;errors=[];records=json.loads((S/'debian-files.lock.json').read_text())['files'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for r in records:
 p=S/'sysroot'/r['path']
 if r['kind']=='symlink':
  if not p.is_symlink() or str(p.readlink())!=r['target']:errors.append(r['path'])
 elif not p.is_file() or p.is_symlink() or sha(p)!=r['sha256'] or (p.stat().st_mode&0o7777)!=r['mode']:errors.append(r['path'])
for p in json.loads((S/'debian-packages.lock.json').read_text())['packages']:
 file=S/'apt/archives'/pathlib.Path(p['filename']).name
 if sha(file)!=p['sha256']:errors.append(p['filename'])
r={'success':not errors,'checked_files_and_symlinks':len(records),'errors':errors};print(json.dumps(r,indent=2));raise SystemExit(not r['success'])
