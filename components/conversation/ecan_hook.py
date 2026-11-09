"""Private-runtime ECAN invocation; no private source copied into this component."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(os.environ['ROKO_SYMBOLIC_ROOT'])
sys.path.insert(0, str(root / 'source'))
from gateway import run_native
from ecan_guest_contract import make_request

if __name__ == '__main__':
    data = json.loads(sys.stdin.buffer.read(20001))
    candidates = data['candidates']
    request = make_request(task_id='conversation-context', revision=1,
        snapshot_sha256=hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
        candidates=candidates, focus_capacity=data['focus_size'], selection_count=min(4, len(candidates)))
    result, receipt = run_native('ecan', request,
        '541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0',
        outer_deadline=time.monotonic()+60)
    print(json.dumps({'result':result, 'receipt':receipt}))
