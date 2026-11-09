#!/usr/bin/env python3
"""Finite actual Omega imports/configuration, with network denial and no agent loop."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from verify import ROOT, verify
_,errors=verify()
if errors:raise SystemExit(str(errors))
python=Path(os.environ.get('OMEGA_COMPONENT_PYTHON',str(ROOT/'.venv/bin/python'))).absolute()
site=Path(subprocess.check_output([str(python),'-c','import sysconfig; print(sysconfig.get_paths()["purelib"])'],text=True).strip())
with tempfile.TemporaryDirectory(prefix='omega-components-',dir=ROOT) as d:
    work=Path(d)
    (work/'repos').symlink_to(ROOT/'vendor/PeTTa/repos',target_is_directory=True)
    source=work/'bounded-startup.metta'
    source.write_bytes((ROOT/'integration/bounded-startup.metta').read_bytes())
    env={'PATH':str(ROOT/'runtime/swipl/bin')+':/usr/bin:/bin',
         'HOME':d,'TMPDIR':d,'PYTHONHOME':sys.base_prefix,
         'LD_LIBRARY_PATH':str(Path(sys.base_prefix)/'lib'),
         'PYTHONPATH':os.pathsep.join([str(site),str(ROOT/'vendor/PeTTa/repos/Omega')]),
         'OPENAI_API_KEY':'not-a-real-key-component-test-only',
         'ANONYMIZED_TELEMETRY':'False','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    command=[str(python),str(ROOT/'scripts/no-internet.py'),'sh',str(ROOT/'vendor/PeTTa-omega-release/run.sh'),str(source),'provider=Test','maxNewInputLoops=0','maxWakeLoops=0','memoryDirectory='+d]
    try:
        result=subprocess.run(command,cwd=work,env=env,capture_output=True,text=True,timeout=90)
    except subprocess.TimeoutExpired as e:
        print('FAIL: component startup exceeded 90 seconds');raise SystemExit(1)
    print(result.stdout,end='');print(result.stderr,end='')
    passes=result.stdout.count('✅')
    failed=result.returncode!=0 or 'ERROR:' in result.stderr or '❌' in result.stdout or passes!=6
    print(json.dumps({'returncode':result.returncode,'checks_passed':passes,'expected_checks':6,'success':not failed,'scope':'Omega imports + initConfig/initLoop/initLogger + temporary Chroma vector roundtrip; no agent loop or model'},indent=2))
    raise SystemExit(int(failed))
