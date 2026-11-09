"""Add an explicitly qualified imported package snapshot to ordinary v2 context."""
import argparse
import json
from pathlib import Path
from fresh import load_profile,digest
from package_awareness import validate_profile


def main():
    parser=argparse.ArgumentParser()
    for name in ('profile','manifest','evidence-root','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();profile=load_profile(args.profile)
    if 'package_awareness' in profile:raise ValueError('Package awareness already configured')
    path=args.manifest.resolve(strict=True);manifest=json.loads(path.read_bytes())
    from components.os_atomspace.conversation_gateway import verify_profile
    verify_profile(manifest)
    for name,sha in manifest['files'].items():
        if name in profile['files'] and profile['files'][name]!=sha:raise ValueError('Conflicting package source pin')
        profile['files'][name]=sha
    profile['files'][str(path)]=digest(path)
    profile['package_awareness']={'manifest':str(path),'sha256':digest(path),
        'evidence_root':str(args.evidence_root.absolute())}
    validate_profile(profile)
    with args.output.open('x') as stream:json.dump(profile,stream,sort_keys=True)
    load_profile(args.output)


if __name__=='__main__':main()
