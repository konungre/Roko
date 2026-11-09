#!/usr/bin/env python3
"""Read-only preflight. Does not install, import Omega, or start an agent."""
import importlib.metadata
import json
import re
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
report={'swipl':None,'janus':False,'requirements':{},'runtime_ready':False}
exe=shutil.which('swipl')
if exe:
    version=subprocess.run([exe,'--version'],capture_output=True,text=True,timeout=10)
    report['swipl']=version.stdout.strip()
    m=re.search(r'(\d+)\.(\d+)\.(\d+)',version.stdout)
    report['swipl_sufficient']=bool(m and tuple(map(int,m.groups())) >= (10,0,2))
    janus=subprocess.run([exe,'-q','-g','use_module(library(janus)),halt','-t','halt(1)'],capture_output=True,text=True,timeout=10)
    report['janus']=janus.returncode==0
for line in (ROOT/'vendor/PeTTa/repos/Omega/requirements.txt').read_text().splitlines():
    name, expected=line.split('==')
    try: actual=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: actual=None
    report['requirements'][name]={'expected':expected,'installed':actual,'matches':actual==expected}
report['runtime_ready']=bool(report.get('swipl_sufficient') and report['janus'] and all(x['matches'] for x in report['requirements'].values()))
report['limitations']='Preflight only; matching versions do not prove integration or offline readiness.'
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['runtime_ready'] else 2)
