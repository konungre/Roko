"""Validate authored plan consistency. No upstream imports or execution."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

def validate():
    registry=json.loads((ROOT/'component-registry.json').read_text())
    sources=json.loads((ROOT/'upstream-provenance.json').read_text())
    evidence=json.loads((ROOT/'current-local-evidence.json').read_text())
    hashes=json.loads((ROOT/'source-hash-checks.json').read_text())
    expected={'mork','metamo','metta_motto','metta_nars','nace','moses','ai_dsl','airis','primus','predictive_causal_coding','transweave'}
    rows=registry['components'];assert {r['id'] for r in rows}==expected and len(rows)==11
    repos={r['repo']:r for r in sources['repositories']};assert len(repos)==12
    count=0
    for r in rows:
        assert r['authority']=='advisory_only' and r['authorizes_actions'] is False
        assert r['persistent_write_authority'] is False and r['guest_qualified'] is False
        assert r['integrated'] is False
        assert r['current_native_tested'] is (r['id']=='metta_nars')
        if r['id']=='metta_nars':
            assert r['native_receipt']['sha256']=='73e9fddbcaa7d39ef6347e846f338b752bcb510b6273db5614a7222ca510f191'
        assert all(name in repos for name in r['repos'])
        for key in ('role','input','output','state','blockers','next_gate'):assert r[key]
    for repo in repos.values():
        assert re.fullmatch('[0-9a-f]{40}',repo['commit'])
        assert repo['tree_truncated'] is False
        for f in repo['files']:
            assert re.fullmatch('[0-9a-f]{40}',f['git_blob_sha'])
            assert re.fullmatch('[0-9a-f]{64}',f['sha256'])
            assert f['bytes']>0 and '/blob/'+repo['commit']+'/' in f['url']
            count+=1
    assert count==49 and len(hashes['checks'])==49
    assert all(c['git_blob_matches'] and c['computed_git_blob']==c['returned_git_blob'] for c in hashes['checks'])
    native=next(r for r in evidence['records'] if r['path']=='symbolic-granite-v7/proof/native-attempt-001/result.json')
    assert native['present'] and native['sha256']=='40d900a2b4a6482144eb783fd737e502d3041688f4e9dac4030cccb4cdc7223f'
    assert evidence['current_native_reruns_by_this_review']==0
    assert registry['milestones']==['A'+str(i) for i in range(10)]
    return {'status':'passed','scope':'Authored registry/provenance consistency only; no native runtime executed',
      'requested_requirements':11,'repository_snapshots':12,'source_blob_checks':49,
      'milestones':10,'source_only_targets_not_promoted':True,'native_execution':False}

if __name__=='__main__':
    result=validate();(ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
