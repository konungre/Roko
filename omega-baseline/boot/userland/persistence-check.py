"""Two-boot checkpoint probe: write once, then restore in another guest."""
import json
import subprocess
import sys

BASE = [sys.executable, '/opt/roko/scripts/roko.py', '--state-dir', '/var/lib/roko']
def run(*args):
    return subprocess.check_output([*BASE, *args], text=True)

if sys.argv[1:] == ['save']:
    run('create', 'durable-state', '--goal', 'Recover this state after guest poweroff')
    run('evidence', 'durable-state', 'source', '--source', 'fixture:persistence', '--text', 'Arithmetic: 7 * 8.')
    run('propose', 'durable-state', '--tool', 'record_answer', '--arguments', '{"text":"56"}', '--evidence', 'source')
    run('check', 'durable-state', '--checker', 'arithmetic')
    run('close', 'durable-state')
    subprocess.check_call([sys.executable, '/opt/roko/persistence.py', 'save'])
elif sys.argv[1:] == ['load']:
    subprocess.check_call([sys.executable, '/opt/roko/persistence.py', 'load'])
    saved = json.loads(run('show', 'durable-state'))
    assert saved['state']['phase'] == 'closed'
    assert saved['state']['goal'] == 'Recover this state after guest poweroff'
    assert saved['state']['executed_actions'] == 0
    assert saved['state']['verification']['authorizes_actions'] is False
    print('ROKO_PERSISTENCE_RECOVERY_PASSED', flush=True)
else:
    raise SystemExit('Expected save or load')
