#!/usr/bin/env python3
"""Check the staged source closure with existing official CPython, not a VM."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'build-src/basilisk-stage'
SYSROOT = STAGE / 'sysroot'
OVERLAY = ROOT / 'build-src/granite-guest-stage/source-v2/opt/roko'


def main():
    records = {r['path']: r for r in json.loads((STAGE / 'debian-files.lock.json').read_text())['files']}
    hashes = {}
    for relative in ('usr/bin/python3.13', 'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'):
        path = SYSROOT / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.is_symlink() or records[relative]['kind'] != 'file' or records[relative]['sha256'] != digest:
            raise ValueError('Official Python runtime mismatch')
        hashes[relative] = digest
    program = r'''
import sys,json
from pathlib import Path
root=Path(sys.argv[1])
sys.path[:0]=[str(root/'vendor/guest-python'),str(root/'vendor/PeTTa/repos/Omega/src'),str(root/'adapters')]
import yaml,config,providers,granite_guest
assert yaml.__with_libyaml__ is False
assert yaml.safe_load('limit: 64')['limit']==64
p=granite_guest.GraniteGuestProvider(root)
assert isinstance(p,providers.LLMProvider)
t=providers.LLMTool().with_name('record_answer').with_description('Inert data only').add_parameter(providers.LLMToolParameter().with_name('text'))
req=providers.LLMRequest().with_messages([providers.llmRequestMessage('user','Repeat ready')]).with_max_tokens(64).with_tools([t])
assert granite_guest.render_prompt(req).endswith('<|start_of_role|>assistant<|end_of_role|>')
r=granite_guest.parse_tool('<tool_call>{"name":"record_answer","arguments":{"text":"ready"}}</tool_call>',req)
r=providers._validate_response(req,r)
assert not r.is_error() and not r.calls[0].is_error()
assert providers.llmResponseToSExpr(r)=='((granite-guest-proposal-0 (record_answer "ready")))'
try:p.start()
except ValueError as e:assert 'binary admission' in str(e)
else:raise AssertionError('Unbuilt provider activated')
print(json.dumps({'python':sys.version,'source_closure_import':True,'pure_python_yaml':True,'actual_omega_validation':True,'unbuilt_provider_fail_closed':True,'model_inference_executed':False}))
'''
    command = [str(SYSROOT / 'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),
               '--library-path', str(SYSROOT / 'usr/lib/x86_64-linux-gnu'),
               str(SYSROOT / 'usr/bin/python3.13'), '-S', '-B', '-c', program, str(OVERLAY)]
    result = subprocess.run(command, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
                                         'PYTHONHOME': str(SYSROOT / 'usr')},
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    report = json.loads(result.stdout)
    report.update(scope='Official guest Python binary executed on host; not guest boot or native inference',
                  python_runtime_hashes=hashes, parent_python=os.sys.version)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
