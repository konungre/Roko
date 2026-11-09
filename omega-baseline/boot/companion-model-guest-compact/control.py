#!/usr/bin/env python3
import json,re,sys,time
from pathlib import Path
attempt=sys.argv[1]
if not re.fullmatch('attempt-[1-9][0-9]*',attempt):raise SystemExit('Exact attempt required')
root=Path(__file__).resolve().parents[2]/'results/companion-model-guest'/attempt/'commands'
if not root.is_dir():raise SystemExit('No combined command inbox')
progress=json.loads((root.parent/'progress.json').read_text())
if progress['status']!='running' or time.time()-progress['heartbeat_unix_seconds']>20:raise SystemExit('No current running heartbeat')
a=json.loads(sys.argv[2]);name=str(time.time_ns());p=root/(name+'.tmp');p.write_text(json.dumps(a)+'\n');p.rename(root/(name+'.json'));print(name)
