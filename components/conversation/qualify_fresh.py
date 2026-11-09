#!/usr/bin/env python3
"""Record a NEW fresh-build closure; never edit historical recovery identities.

Run only after reviewing the source/build provenance of both runtime inputs.
This records bytes; real model and conversation qualification is a separate probe.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbolic-profile', type=Path, required=True)
    parser.add_argument('--infer', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refuse to replace a qualification profile')
    profile = json.loads(args.symbolic_profile.read_text())
    for path, expected in profile['files'].items():
        if sha(path) != expected:
            raise ValueError('Symbolic profile changed: '+path)
    profile.update(kind='roko-fresh-host-v1', infer=str(args.infer.resolve(strict=True)),
                   model=str(args.model.resolve(strict=True)),
                   qualification='Prepared; requires actual native conversation probe')
    paths = [args.infer.resolve(),args.model.resolve()]
    # Resolve dynamic libraries for this newly built trusted executable.
    listing = subprocess.run(['ldd',profile['infer']],check=True,text=True,capture_output=True)
    if 'not found' in listing.stdout:
        raise ValueError('Missing native library')
    for line in listing.stdout.splitlines():
        for word in line.split():
            if word.startswith('/'):
                paths.append(Path(word))
    source = Path(__file__).resolve().parent
    paths += [p for p in source.iterdir() if p.suffix in ('.py','.pl','.metta','.cpp')]
    paths += [source.parents[1]/'omega-baseline/scripts/no-network.py']
    profile['files'].update({str(p):sha(p) for p in paths})
    from fresh import load_profile
    # Write once; verification errors remain explicit evidence, not rewritten locks.
    with args.output.open('x') as stream:
        json.dump(profile,stream,indent=2)
        stream.write('\n')
    load_profile(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
