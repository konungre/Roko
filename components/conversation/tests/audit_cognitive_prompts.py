"""Bind captured fifth/sixth native prompts to complete history and cognition."""
import argparse,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovered import render,system_message
p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory
n=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
requests=[json.loads(x) for x in (root/'requests.jsonl').read_text().splitlines()]
checks={}
for i,count in enumerate((8,10)):
 system=system_message(SimpleNamespace(context=[],cognitive_context=n['cognitive_history']))
 prompt=render([{'role':'system','content':system}]+n['history'][:count]+[{'role':'user','content':requests[i]['text']}])
 checks['prompt_'+str(i+5)]=hashlib.sha256(prompt.encode()).hexdigest()==n['native_calls'][i]['prompt_sha256']
r={'passed':all(checks.values()),'checks':checks,'observations':len(n['cognitive_history'])};(root/'prompt-audit.json').write_text(json.dumps(r,indent=2)+'\n');print(r);raise SystemExit(0 if r['passed'] else 1)
