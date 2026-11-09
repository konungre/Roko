#!/usr/bin/env python3
"""Queue one authorized diagnostic action for the already-running bounded guest."""
import json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'results/roko-corner-guest/commands'
if not root.is_dir():raise SystemExit('No running avatar control inbox')
a=json.loads(sys.argv[1]);name=str(time.time_ns());p=root/(name+'.tmp');p.write_text(json.dumps(a)+'\n');p.rename(root/(name+'.json'));print(name)
