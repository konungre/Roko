#!/usr/bin/env python3
"""Verify actual Debian archive facts through real PeTTa/Janus, without executing packages.

Run from any directory: python integration/package_inventory_native_test.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / 'adapters'))
from package_inventory import load_inventory, atoms

def main():
    inventory = load_inventory(verify_archives=True)
    facts = atoms(inventory)
    checks = ['!(test (py-call (package_inventory_bridge.initialize)) ' + str(len(inventory['packages'])) + ')']
    for row in inventory['packages']:
        name = json.dumps(row['package']); arch = json.dumps(row['architecture'])
        checks.append(f'!(test (match &self (workspace-deb {name} $version {arch} $sha) (py-call (package_inventory_bridge.matches {name} $version {arch} $sha))) true)')
    check_count = len(checks)
    python = Path(os.environ.get('OMEGA_MODEL_PYTHON', str(ROOT / '.venv/bin/python'))).absolute()
    site = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_paths()["purelib"])'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='package-native-', dir=ROOT) as d:
        work = Path(d)
        (work / 'repos').symlink_to(ROOT / 'vendor/PeTTa/repos', target_is_directory=True)
        source = work / 'package-planning.metta'
        source.write_text('!(import! &self ' + json.dumps(str(ROOT / 'integration/package_inventory_bridge.py')) + ')\n' + facts + '\n'.join(checks) + '\n')
        env = {'PATH': str(ROOT / 'runtime/swipl/bin') + ':/usr/bin:/bin', 'HOME':d, 'TMPDIR':d,
               'PYTHONHOME':sys.base_prefix, 'LD_LIBRARY_PATH':str(Path(sys.base_prefix)/'lib'),
               'PYTHONPATH':os.pathsep.join([site, str(ROOT / 'adapters')]), 'PYTHONDONTWRITEBYTECODE':'1'}
        result = subprocess.run([str(python), str(ROOT / 'scripts/no-internet.py'), 'sh', str(ROOT / 'vendor/PeTTa-omega-release/run.sh'), str(source)], cwd=work, env=env, capture_output=True, text=True, timeout=120)
    log = result.stdout + result.stderr
    out = ROOT / 'results/package-inventory-native.txt'
    out.write_text(log)
    passed = result.returncode == 0 and 'ERROR:' not in log and '❌' not in log and log.count('✅') == check_count
    report = {'passed':passed, 'native_contract_assertions':check_count, 'runtime':'Existing PeTTa v1.0.4 / SWI-Prolog Janus',
              'input_kind':'Actual workspace Debian archive lock and locally rehashed archives', 'inventory':inventory, 'package_changes_executed':0,
              'live_nix_observed':False, 'log':str(out.relative_to(ROOT))}
    (ROOT / 'results/package-inventory-native.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if passed else 1

if __name__ == '__main__': raise SystemExit(main())
