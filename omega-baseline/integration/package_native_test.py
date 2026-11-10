#!/usr/bin/env python3
"""Run the real PeTTa/Janus planner contract offline, no package mutations.

Run from any directory: python integration/package_native_test.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    python = Path(os.environ.get('OMEGA_MODEL_PYTHON', str(ROOT / '.venv/bin/python'))).absolute()
    site = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_paths()["purelib"])'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='package-native-', dir=ROOT) as d:
        work = Path(d)
        (work / 'repos').symlink_to(ROOT / 'vendor/PeTTa/repos', target_is_directory=True)
        source = work / 'package-planning.metta'
        source.write_text((ROOT / 'integration/package_planning.metta').read_text().replace('__BRIDGE__', str(ROOT / 'integration/package_bridge.py')))
        env = {'PATH': str(ROOT / 'runtime/swipl/bin') + ':/usr/bin:/bin', 'HOME':d, 'TMPDIR':d,
               'PYTHONHOME':sys.base_prefix, 'LD_LIBRARY_PATH':str(Path(sys.base_prefix)/'lib'),
               'ROKO_PACKAGE_PLANNER':os.environ.get('ROKO_PACKAGE_PLANNER','legacy'),
               'PYTHONPATH':os.pathsep.join([site, str(ROOT / 'adapters')]), 'PYTHONDONTWRITEBYTECODE':'1'}
        result = subprocess.run([str(python), str(ROOT / 'scripts/no-internet.py'), 'sh', str(ROOT / 'vendor/PeTTa-omega-release/run.sh'), str(source)], cwd=work, env=env, capture_output=True, text=True, timeout=120)
    log = result.stdout + result.stderr
    out = ROOT / 'results/package-planning-native.txt'
    out.write_text(log)
    passed = result.returncode == 0 and 'ERROR:' not in log and '❌' not in log and log.count('✅') == 3
    report = {'passed':passed, 'planner_mode':env['ROKO_PACKAGE_PLANNER'], 'native_contract_assertions':3, 'runtime':'Existing PeTTa v1.0.4 / SWI-Prolog Janus',
              'input_kind':'Fixture package path and caller-supplied empty snapshot', 'package_changes_executed':0,
              'live_nix_observed':False, 'log':str(out.relative_to(ROOT))}
    (ROOT / 'results/package-planning-native.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if passed else 1

if __name__ == '__main__': raise SystemExit(main())
