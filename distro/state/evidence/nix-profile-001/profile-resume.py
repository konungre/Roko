import os,json,subprocess
from pathlib import Path
b=Path('/workspace/scratch/nix-live-001');uri='local?store='+str(b/'direct-store')+'&state='+str(b/'direct-state')+'&log='+str(b/'direct-log')
base=[str(b/'root/usr/bin/nix'),'--extra-experimental-features','nix-command flakes','--store',uri,'--offline','--option','build-users-group','','--option','sandbox','false']
env={**os.environ,'LD_LIBRARY_PATH':str(b/'root/usr/lib/x86_64-linux-gnu')};rows=[]
def run(args):
 r=subprocess.run(base+args,env=env,capture_output=True,text=True,timeout=60);rows.append({'argv':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r
run(['profile','remove','--profile',str(b/'profile'),'roko-profile'])
run(['profile','install','--profile',str(b/'profile'),str(b/'direct-store/mk439cr63i5hjg1hvsy0yrzbsvamv54y-roko-profile-2')])
run(['profile','list','--profile',str(b/'profile'),'--json'])
run(['profile','history','--profile',str(b/'profile')])
(b/'profile-final.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
