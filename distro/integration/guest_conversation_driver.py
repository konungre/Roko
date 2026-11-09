"""One bounded real guest conversation request; no UI, history replay or retry."""
import json
import os
from pathlib import Path
import subprocess
import sys

if os.getresuid() != (1000,1000,1000) or os.getresgid() != (1000,1000,1000):
    raise SystemExit('Require guest UID/GID1000')
source=Path('/opt/roko/workspace/components/conversation')
request={'text':'Reply with only the word hello.','context':[]}
proc=subprocess.Popen([sys.executable,'-B',str(source/'fresh_server.py')],
                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                      env={**os.environ,'ROKO_FRESH_PROFILE':'/opt/roko/workspace/profile.json'})
try:
    stdout,stderr=proc.communicate((json.dumps(request)+'\n').encode(),timeout=480)
except subprocess.TimeoutExpired:
    proc.terminate()
    try:stdout,stderr=proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();stdout,stderr=proc.communicate()
    sys.stderr.buffer.write(stderr[-1024*1024:]);raise SystemExit('Guest conversation deadline')
sys.stderr.buffer.write(stderr[-1024*1024:]);sys.stderr.flush()
try:
    lines=stdout.decode().splitlines();assert len(lines)==1
    response=json.loads(lines[0]);assert set(response)=={'text','context_ids','executed_actions'}
    assert isinstance(response['text'],str) and response['text'].strip() and response['context_ids']==[] and response['executed_actions']==0
    receipts=[json.loads(line.removeprefix('ROKO_FRESH_CONVERSATION ')) for line in stderr.decode().splitlines() if line.startswith('ROKO_FRESH_CONVERSATION ')]
    assert proc.returncode==0 and len(receipts)==1 and len(receipts[0]['native_calls'])==1
    call=receipts[0]['native_calls'][0]
    assert call['returncode']==0 and call['model_verified_before_history_commit'] and 'descendants_cleaned=1' in call['stderr']
except (AssertionError,ValueError,KeyError):
    print('ROKO_GUEST_CONVERSATION_FAILED '+json.dumps({'returncode':proc.returncode,'stdout_tail':stdout[-4096:].decode(errors='replace')}),flush=True)
    raise SystemExit(1)
print('ROKO_GUEST_CONVERSATION_PASSED '+json.dumps({'uid':os.getuid(),'response':response,'model_identity_unchanged':receipts[0]['model_identity_unchanged'],'native_seconds':call['seconds']}),flush=True)
