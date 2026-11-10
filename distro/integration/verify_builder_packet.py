"""Check evidence-file correspondence only; never grant builder trust/readiness."""
import argparse,hashlib,json,os,re,stat
from pathlib import Path
REQUIRED={'source-pin.json','sandbox-result.json','roots.json','closure-verification.json','image-hashes.json'}
def verify(directory,manifest,expected_pin):
 directory=Path(directory)
 if directory.resolve()!=directory:raise ValueError('canonical packet directory required')
 if not isinstance(manifest,dict) or set(manifest)!={'schema','status','files'} or manifest['schema']!='roko-builder-packet-v1' or manifest['status']!='unqualified':raise ValueError('unqualified packet manifest required')
 if set(manifest['files'])!=REQUIRED:raise ValueError('required evidence set')
 fd=os.open(directory,os.O_DIRECTORY|os.O_NOFOLLOW);data={}
 try:
  for name,expected in manifest['files'].items():
   if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('digest')
   source=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
   with os.fdopen(source,'rb') as f:
    before=os.fstat(f.fileno())
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>8*1024**2:raise ValueError('bounded single-link regular evidence required')
    raw=f.read(8*1024**2+1);after=os.fstat(f.fileno())
    identity=lambda s:(s.st_ino,s.st_dev,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if len(raw)>8*1024**2 or identity(before)!=identity(after) or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('evidence mismatch or mutation')
    data[name]=json.loads(raw)
 finally:os.close(fd)
 if data['source-pin.json']!=expected_pin:raise ValueError('unexpected source pin')
 return {'artifact_hashes_match':True,'source_pin_matches':True,'builder_signature_verified':False,'sandbox_evidence_independently_replayed':False,'closure_trust_verified':False,'image_ready':False,'execution_authorized':False,'scope':'file correspondence, not semantic evidence or authority'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('manifest');p.add_argument('expected_pin');a=p.parse_args();r=verify(Path(a.directory).resolve(),json.loads(Path(a.manifest).read_text()),json.loads(Path(a.expected_pin).read_text()));print(json.dumps(r))
