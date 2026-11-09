#!/usr/bin/env python3
import pathlib,json,subprocess,configparser,concurrent.futures,sys
S=pathlib.Path(__file__).resolve().parent;R=S.parents[1];lock=json.loads((R/'boot/cosmic-source.lock.json').read_text());config=configparser.ConfigParser();config.read(R/'build-src/cosmic-epoch-research/.gitmodules');urls={config[x]['path']:config[x]['url'] for x in config.sections() if "url" in config[x]};existing=json.loads((S/'sources.lock.json').read_text());records={x['component']:x for x in existing['components']}
def fetch(name):
 p=S/'sources'/name;rev=lock['submodule_gitlinks'][name];url=urls[name]
 if not p.exists():
  subprocess.run(['git','init','-q',str(p)],check=True);subprocess.run(['git','-C',str(p),'remote','add','origin',url],check=True)
 subprocess.run(['git','-C',str(p),'fetch','--depth=1','origin',rev],check=True,stdout=subprocess.DEVNULL);subprocess.run(['git','-C',str(p),'checkout','--detach','-q',rev],check=True);assert subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()==rev
 return {'component':name,'url':url,'commit':rev,'path':str(p.relative_to(R))}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for x in pool.map(fetch,sys.argv[1:]):records[x['component']]=x
existing['components']=list(records.values());(S/'sources.lock.json').write_text(json.dumps(existing,indent=2)+'\n');print('Exact source checkouts:',len(records))
