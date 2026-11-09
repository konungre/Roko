#!/usr/bin/env python3
"""Two frozen direct Omega cases, unchanged four-thread model runtime."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'boot/granite-model-guest-fourcore'))
import prepare_fourcore as previous
sha=previous.sha
synthetic_proof=previous.synthetic_proof
RECEIPT_SHA=previous.RECEIPT_SHA
OUT=ROOT/'build-src/granite-model-guest-stage/candidate-v5-two-fixed-cases'
PACK=ROOT/'boot/granite-guest-representative'
CASE_IDS=['literal_copy','invoice_extraction']


def case_plan():
    fixed=json.loads((PACK/'fixtures.json').read_text())
    prep=json.loads((ROOT/'results/granite-guest-representative-preparation/plan.json').read_text())
    lookup={x['id']:x for x in fixed['cases']}
    observations={x['id']:x for x in prep['cases']}
    return {'case_ids':CASE_IDS,'fixture_sha256':sha((PACK/'fixtures.json').read_bytes()),
            'request_envelope':'Unchanged historical direct Omega system/tool/prompt envelope, not the UI/CLI wrapper',
            'cases':[{**lookup[name],**{key:observations[name][key] for key in ('rendered_prompt_sha256','grammar_sha256','historical_host_prompt_tokens')}} for name in CASE_IDS],
            'native_seconds_per_request':900,'provider_seconds_per_request':930,
            'vm_seconds':2100,'total_runner_seconds':2400,'retries':0,
            'expected_wrong_invoice':{'invoice':'Invoice A17','total':'42.50'},
            'wrong_answer_policy':'Record exact accuracy failure and actual controller rejection; never count it as a successful model answer'}


def validate():
    previous.validate()
    old=json.loads((previous.OUT/'manifest.json').read_text())
    current=json.loads((OUT/'manifest.json').read_text())
    additions={'evaluation/guest_cases.py','evaluation/fixtures.json','evaluation/cases.lock.json'}
    if set(current['files']) != set(old['files'])|additions:
        raise ValueError('Unexpected representative payload files')
    for name,pin in old['files'].items():
        if name!='granite-portable-runtime.lock.json' and current['files'][name]!=pin:
            raise ValueError('Existing four-thread runtime changed: '+name)
    for name,pin in current['files'].items():
        data=(OUT/'roko'/name).read_bytes()
        if sha(data)!=pin['sha256'] or len(data)!=pin['bytes']:
            raise ValueError('Representative candidate changed: '+name)
    for name in ('guest_cases.py','fixtures.json'):
        if (OUT/'roko/evaluation'/name).read_bytes() != (PACK/name).read_bytes():
            raise ValueError('Frozen fixture helper changed')
    if json.loads((OUT/'roko/evaluation/cases.lock.json').read_text())!=case_plan():
        raise ValueError('Frozen selected case plan changed')
    return current


def main():
    previous.validate()
    if OUT.exists():raise ValueError('Preserve existing prepared candidate')
    old=json.loads((previous.OUT/'manifest.json').read_text())
    files={name:(previous.OUT/'roko'/name).read_bytes() for name in old['files']}
    modes={name:pin['mode'] for name,pin in old['files'].items()}
    for name in ('guest_cases.py','fixtures.json'):
        files['evaluation/'+name]=(PACK/name).read_bytes();modes['evaluation/'+name]=0o444
    files['evaluation/cases.lock.json']=(json.dumps(case_plan(),indent=2)+'\n').encode();modes['evaluation/cases.lock.json']=0o444
    runtime=json.loads(files['granite-portable-runtime.lock.json'])
    runtime['files']={name:sha(data) for name,data in files.items() if name!='granite-portable-runtime.lock.json'}
    files['granite-portable-runtime.lock.json']=(json.dumps(runtime,indent=2)+'\n').encode()
    OUT.mkdir(mode=0o700)
    for name,data in files.items():
        path=OUT/'roko'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(modes[name])
    report={'status':'prepared-two-fixed-cases','parent_manifest_sha256':sha((previous.OUT/'manifest.json').read_bytes()),
            'model_read':False,'native_rebuilt':False,'case_plan':case_plan(),'payload_bytes':sum(map(len,files.values())),
            'files':{name:{'sha256':sha(data),'bytes':len(data),'mode':modes[name]} for name,data in files.items()}}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');validate()
    print(json.dumps({key:report[key] for key in ('status','model_read','native_rebuilt','payload_bytes','case_plan')},indent=2))

if __name__=='__main__':main()
