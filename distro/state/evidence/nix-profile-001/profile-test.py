import os,json,subprocess
from pathlib import Path
b=Path('/workspace/scratch/nix-live-001');uri='local?store='+str(b/'direct-store')+'&state='+str(b/'direct-state')+'&log='+str(b/'direct-log')
base=[str(b/'root/usr/bin/nix'),'--extra-experimental-features','nix-command flakes','--store',uri,'--offline','--option','build-users-group','','--option','sandbox','false']
env={**os.environ,'LD_LIBRARY_PATH':str(b/'root/usr/lib/x86_64-linux-gnu')};rows=[]
def run(args):
 r=subprocess.run(base+args,env=env,capture_output=True,text=True,timeout=60);rows.append({'argv':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r
for revision in (1,2):
 script='/bin/mkdir -p "$out/share"; printf '+str(revision)+' > "$out/share/roko-generation"'
 expr='builtins.derivation { name="roko-profile-'+str(revision)+'"; system=builtins.currentSystem; builder="/bin/sh"; args=["-c" '+json.dumps(script)+']; }'
 p=b/('profile-'+str(revision)+'.nix');p.write_text(expr)
 r=run(['build','--impure','--file',str(p),'--no-link','--json'])
 if r.returncode:break
 output=json.loads(r.stdout)[0]['outputs']['out']
 args=['profile','install','--profile',str(b/'profile'),output] if revision==1 else ['profile','upgrade','--profile',str(b/'profile'),'0']
 # Explicit replacement creates native profile generations without changing host PATH.
 if revision==2:
  if run(['profile','remove','--profile',str(b/'profile'),'0']).returncode:break
  args=['profile','install','--profile',str(b/'profile'),output]
 if run(args).returncode:break
 run(['profile','list','--profile',str(b/'profile'),'--json'])
(b/'profile-results.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows[-2:],indent=2))
