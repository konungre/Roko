"""Add an explicitly qualified imported package snapshot to ordinary v2 context."""
import argparse
import json
import time
from pathlib import Path
from fresh import load_profile,digest
from package_awareness import validate_profile


def main():
    parser=argparse.ArgumentParser()
    for name in ('profile','manifest','evidence-root','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--receipt-policy',choices=['strict','explain_v1'],default='strict')
    parser.add_argument('--max-admission-age-seconds',type=int)
    args=parser.parse_args();profile=load_profile(args.profile)
    if 'package_awareness' in profile:raise ValueError('Package awareness already configured')
    path=args.manifest.resolve(strict=True);manifest=json.loads(path.read_bytes())
    from components.os_atomspace.conversation_gateway import verify_profile,verify_runtime
    optional=set()
    if args.receipt_policy=='explain_v1':
        if args.max_admission_age_seconds is None:raise ValueError('Explicit admission age required')
        verify_runtime(manifest);optional={manifest['facts_path'],manifest['receipts_path']}
    else:
        if args.max_admission_age_seconds is not None:raise ValueError('Admission age requires explain_v1')
        verify_profile(manifest)
    for name,sha in manifest['files'].items():
        if name in optional:
            if name in profile['files']:raise ValueError('Source data required by base profile cannot become optional')
            continue
        if name in profile['files'] and profile['files'][name]!=sha:raise ValueError('Conflicting package source pin')
        profile['files'][name]=sha
    profile['files'][str(path)]=digest(path)
    profile['package_awareness']={'manifest':str(path),'sha256':digest(path),
        'evidence_root':str(args.evidence_root.absolute())}
    if args.receipt_policy=='explain_v1':
        profile['package_awareness'].update(receipt_policy='explain_v1',qualified_at_ns=time.time_ns(),
            max_admission_age_seconds=args.max_admission_age_seconds)
    validate_profile(profile)
    with args.output.open('x') as stream:json.dump(profile,stream,sort_keys=True)
    load_profile(args.output)


if __name__=='__main__':main()
