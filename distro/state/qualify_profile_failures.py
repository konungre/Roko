"""Native missing/corrupt rollback observations in private disposable profiles."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from profile_switch import Profiles

def qualify(base,out):
 base,out=map(lambda x:Path(x).resolve(),(base,out));out.mkdir(mode=0o700)
 p=Profiles(out/'profiles',str(base/'root/usr/bin/nix'),'local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log'),{**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')})
 outputs=[]
 for n in (1,2):
  outputs.append(json.loads(p.run('--option','build-users-group','','--option','sandbox','false','build','--impure','--file',str(base/f'profile-{n}.nix'),'--no-link','--json'))[0]['outputs']['out'])
 first=p.switch({'roko':outputs[0]},p.current(),True)
 second=p.switch({'roko':outputs[1]},p.current(),True)
 target=Path(first['after']['target']);saved=target.parent/'profile.saved';native=target.resolve()
 original=hashlib.sha256((native/'manifest.json').read_bytes()).hexdigest()
 expected=p.current();failures=[]
 # Only the private profile symlink is moved; the native store remains immutable.
 target.rename(saved)
 try:
  try:p.rollback(str(target),expected,True)
  except (ValueError,RuntimeError) as e:failures.append({'case':'missing-target','rejected':True,'error':str(e),'active_unchanged':p.current()==expected})
  else:raise AssertionError('missing target accepted')
 finally:saved.rename(target)
 corrupt=out/'corrupt-profile-copy';shutil.copytree(native,corrupt,symlinks=True);corrupt.chmod(0o700)
 manifest=corrupt/'manifest.json'
 if manifest.is_symlink():raise ValueError('fixture manifest must be a copied regular file')
 manifest.chmod(0o600);manifest.write_text('{invalid-json')
 target.rename(saved);os.symlink(str(corrupt),target)
 try:
  try:p.rollback(str(target),expected,True)
  except (ValueError,RuntimeError) as e:failures.append({'case':'corrupt-native-manifest','rejected':True,'error':str(e),'active_unchanged':p.current()==expected})
  else:raise AssertionError('corrupt target accepted')
 finally:target.unlink();saved.rename(target)
 # A parseable but different generation must also fail receipt identity checks.
 other=Path(second['after']['target']).resolve()/'manifest.json'
 manifest.write_bytes(other.read_bytes())
 target.rename(saved);os.symlink(str(corrupt),target)
 try:
  try:p.rollback(str(target),expected,True)
  except (ValueError,RuntimeError) as e:failures.append({'case':'valid-wrong-generation','rejected':True,'error':str(e),'active_unchanged':p.current()==expected})
  else:raise AssertionError('wrong generation accepted')
 finally:target.unlink();saved.rename(target)
 rollback=p.rollback(str(target),expected,True)
 unchanged=original==hashlib.sha256((native/'manifest.json').read_bytes()).hexdigest()
 payload=(p.root/'active/share/roko-generation').read_text()
 passed=len(failures)==3 and all(x['rejected'] and x['active_unchanged'] for x in failures) and unchanged and payload=='1' and rollback['after']['revision']==3
 report={'passed':passed,'failures':failures,'rollback':rollback,'original_store_manifest_unchanged':unchanged,'restored_payload':payload,'host_activation':False,'scope':'private profile symlink/copy fault fixtures; original Nix store bytes unchanged'}
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('output');a=p.parse_args();r=qualify(a.base,a.output);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
