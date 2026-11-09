"""Read-only CLI/checkpoint and process inspection after genuine UI exit."""
import json,subprocess,sys
from pathlib import Path
root=Path('/run/granite-model-probe/roko');state='/root/.local/state/roko-combined'
cmd=[sys.executable,str(root/'scripts/roko.py'),'--state-dir',state]
listed=subprocess.run(cmd+['list'],capture_output=True,text=True,timeout=10)
report={'list_returncode':listed.returncode,'tasks':[],'processes':[]}
if listed.returncode==0:
 for task in json.loads(listed.stdout):
  shown=subprocess.run(cmd+['show',task['task']],capture_output=True,text=True,timeout=10)
  report['tasks'].append({'returncode':shown.returncode,'result':json.loads(shown.stdout) if shown.returncode==0 else shown.stderr})
for proc in Path('/proc').glob('[0-9]*'):
 try:
  raw=(proc/'cmdline').read_bytes();comm=(proc/'comm').read_text().strip()
  if comm=='roko-window-tra' or any(x in raw for x in [b'/runtime/granite/',b'/corner/observe.py']):report['processes'].append({'pid':int(proc.name),'comm':comm,'cmdline':raw.decode(errors='replace').replace('\0',' ')})
 except (FileNotFoundError,ProcessLookupError):pass
print('ROKO_COMBINED_INSPECTION '+json.dumps(report),flush=True)
