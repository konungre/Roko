#!/usr/bin/env python3
"""Deterministic offline tests of the actual ECAN attention-bank bridge."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters'))
from native_ecan import rank_candidates, ROOT

def main():
    lock=json.loads((ROOT/'metta-attention-source.lock.json').read_text())
    source=ROOT/'build-src/metta-attention-research'
    def hashes():return {name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in lock['files']}
    before=hashes();assert before==lock['files']
    fixture=[{'id':'candidate_a','sti':200,'lti':100,'stimulus':2},
             {'id':'candidate_b','sti':230,'lti':20,'stimulus':0}]
    original=copy.deepcopy(fixture);start=time.monotonic();checks=[]
    actual=rank_candidates(fixture,focus_size=1)
    assert actual['ranking']==[{'id':'candidate_a','sti':240.0,'lti':140.0,'in_focus':True},
                               {'id':'candidate_b','sti':230.0,'lti':20.0,'in_focus':False}]
    checks.append('Native stimulus updates STI and LTI and reverses original ranking')
    assert actual['focus']==['candidate_a'];checks.append('Actual native focus respects capacity one')
    assert actual['funds']=={'sti':99530.0,'lti':99840.0};checks.append('Native bank conserves STI and LTI funds')
    assert fixture==original;checks.append('Caller inputs unchanged')
    assert rank_candidates(fixture,focus_size=1)==actual;checks.append('Repeated fresh native banks produce identical result')
    baseline=copy.deepcopy(fixture);baseline[0]['stimulus']=0
    reset=rank_candidates(baseline,focus_size=1)
    assert reset['ranking'][0]['id']=='candidate_b' and reset['focus']==['candidate_b']
    checks.append('No attention state leaks between calls')
    maximum=[{'id':'candidate_'+str(i),'sti':1000,'lti':1000,'stimulus':10} for i in range(16)]
    max_result=rank_candidates(maximum,focus_size=16)
    assert len(max_result['ranking'])==16 and len(max_result['focus'])==16
    assert all(row['sti']==1200 and row['lti']==1200 for row in max_result['ranking'])
    checks.append('Maximum accepted fixture remains bounded and conserves funds')
    assert all(r['advisory_only'] and not r['authorizes_actions'] and not r['persistent_state_changed'] for r in [actual,reset,max_result])
    checks.append('All results advisory, without action authorization or persistent controller mutation')
    assert hashes()==before;checks.append('All upstream tracked source hashes preserved')
    result={'status':'passed','implementation':actual['implementation'],'commit':lock['commit'],
            'checks':checks,'check_count':len(checks),'example':actual,'seconds':round(time.monotonic()-start,3),
            'scope':'Native bank subset, not full scheduler; no installs or external actions'}
    (ROOT/'results/ecan-native-advisory.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
