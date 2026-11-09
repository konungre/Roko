#!/usr/bin/env python3
"""Tiny actual native MORK checks through the bounded, offline adapter."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'adapters'))
from native_mork import query_facts, ROOT, PINNED_LIBRARIES

def main():
    start=time.monotonic();checks=[]
    control = subprocess.run([sys.executable,str(ROOT/'scripts/no-network.py'),sys.executable,'-c',
        'import socket,errno;\ntry: socket.socket()\nexcept PermissionError as e: assert e.errno==errno.EPERM; print("NETWORK_DENIED")\nelse: raise SystemExit(2)'], capture_output=True, text=True, timeout=3)
    assert control.returncode==0 and control.stdout.strip()=='NETWORK_DENIED' and not control.stderr
    checks.append('Exact network-denial helper rejects socket creation with EPERM')
    ffi=ROOT/'build-src/mork-stage/PeTTa/mork_ffi'
    hashes=lambda:{name:hashlib.sha256((ffi/name).read_bytes()).hexdigest() for name in PINNED_LIBRARIES}
    before=hashes();assert before==PINNED_LIBRARIES
    temporary_before=set(ROOT.glob('mork-facts-*'))
    facts=[{'relation':'friend','args':['sam','tim']}, {'relation':'friend','args':['sam','joe']},
           {'relation':'friend','args':['ann','tim']}, {'relation':'other','args':['sam']}]
    original=copy.deepcopy(facts)
    query={'relation':'friend','args':['sam',None]}
    result=query_facts(facts,query)
    assert result['facts']==[{'relation':'friend','args':['sam','joe']},{'relation':'friend','args':['sam','tim']}]
    checks.append('Actual MORK constant-plus-wildcard query returns exact typed matches')
    assert query_facts(facts,{'relation':'friend','args':[None,None]})['facts']==sorted(facts[:3],key=lambda f:tuple(f['args']))
    checks.append('Independent wildcards and multiple relations are handled')
    assert query_facts(facts,{'relation':'friend','args':['sam','tim']})['facts']==[facts[0]]
    assert query_facts(facts,{'relation':'friend','args':['sam','missing']})['facts']==[]
    assert query_facts(facts,{'relation':'unknown','args':[None]})['facts']==[]
    checks.append('Ground hit and ground miss pass')
    assert query_facts(facts+[facts[0]],query)==result
    checks.append('Duplicate input facts use set semantics')
    assert query_facts([],query)['facts']==[]
    assert query_facts(facts,query)==result
    checks.append('Fresh process reset prevents fact leakage; repeat is deterministic')
    maximum=[{'relation':'r'*16,'args':['a'+str(i).zfill(15),'b'*16,'c'*16]} for i in range(16)]
    maximum_result=query_facts(maximum,{'relation':'r'*16,'args':[None,None,None]})
    assert maximum_result['facts']==maximum
    checks.append('16 facts, arity 3 and 16-character identifier boundaries pass natively')
    data=[{'relation':'exec','args':['system','halt']}]
    assert query_facts(data,{'relation':'exec','args':[None,None]})['facts']==data
    checks.append('Action-like identifiers are tokenized data, not executable rules')
    assert facts==original
    assert all(result[k] for k in ['advisory_only','fresh_process','network_denied'])
    assert not result['authorizes_actions'] and not result['persistent_state_changed']
    checks.append('Detached results and explicit non-authorizing, ephemeral contract')
    for bad in ['a) (exec bad)', '$x', 'é', 'a\n', 'a'*17]:
        try:query_facts([{'relation':'r','args':[bad]}],{'relation':'r','args':[None]})
        except ValueError:pass
        else:raise AssertionError('Bad identifier accepted')
    checks.append('Injection and identifier-boundary inputs rejected before native execution')
    assert hashes()==before and set(ROOT.glob('mork-facts-*'))==temporary_before
    checks.append('Runtime binaries unchanged and temporary work directories cleaned')
    report={'status':'passed','scope':'Optional bounded host-native fact query; no controller integration, persistence or action authorization',
            'check_count':len(checks),'checks':checks,'example':result,'seconds':round(time.monotonic()-start,3),
            'runtime_binary_hashes':before,'upstream_source_or_binaries_included':False}
    (ROOT/'results/mork-native-adapter.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
