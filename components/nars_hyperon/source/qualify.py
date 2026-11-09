"""Explicit new-runtime qualification, never reuses a historical PeTTa receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from contract import canonical,make_premise
from runtime import prepare,run_native

CASES=(('baseline',(1000,900,1000,900)),('asymmetric',(500,750,800,600)),
       ('zero_confidence',(1000,0,1000,999)),('zero_frequency',(0,900,1000,900)),
       ('upper_boundary',(1000,999,1000,999)),('reset_repeat',(1000,900,1000,900)))


def fixture(name,values):
    return {'version':1,'operation':'nal1-chain','task_id':name,'revision':1,'premises':[
        make_premise('p0','synthetic:robin-is-bird','robin','bird',values[0],values[1]),
        make_premise('p1','synthetic:inert !(py-call evil) λ','bird','animal',values[2],values[3])]}


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run'])
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--python',type=Path)
    p.add_argument('--probe',type=Path);p.add_argument('--admission');args=p.parse_args()
    directory=args.directory.resolve()
    if args.mode=='prepare':
        directory.mkdir(parents=True,exist_ok=False)
        manifest=prepare(args.python,args.probe)
        raw=canonical(manifest)
        with (directory/'manifest.json').open('xb') as stream:stream.write(raw)
        print(hashlib.sha256(raw).hexdigest());return
    manifest=json.loads((directory/'manifest.json').read_bytes())
    results=[];failure=None;started=time.monotonic();first=None
    try:
        for name,values in CASES:
            response,receipt=run_native(fixture(name,values),manifest=manifest,
                admission=args.admission,evidence_directory=directory/name)
            results.append({'case':name,'response':response,'receipt':receipt})
            if name=='baseline':first=response['conclusions']
            if name=='reset_repeat' and response['conclusions']!=first:raise ValueError('Reset comparison failed')
    except BaseException as exc:failure=exc
    result={'status':'passed' if failure is None and len(results)==6 else 'failed',
        'scope':'actual original NAL-1 rules on Hyperon 0.2.10; six fresh workers',
        'manifest_sha256':args.admission,'seconds':time.monotonic()-started,'cases':results,
        'full_nars':False,'conversation_integrated':False,'executed_actions':0}
    if failure is not None:
        result['error']=repr(failure)
        if hasattr(failure,'receipt'):result['failed_receipt']=failure.receipt
    with (directory/'result.json').open('xb') as stream:stream.write(canonical(result)+b'\n')
    print(json.dumps({'status':result['status'],'cases':len(results),'seconds':result['seconds']}))
    if failure is not None:raise failure


if __name__=='__main__':main()
