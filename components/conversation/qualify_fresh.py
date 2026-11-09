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


def add_mork_profile(profile, manifest_path, manifest_sha256):
    """Pin a reviewed native closure; this does not claim a successful query."""
    if manifest_path is None and manifest_sha256 is None:
        return
    if manifest_path is None or manifest_sha256 is None:
        raise ValueError('Both MORK qualification options are required')
    from mork_host import RebuiltMORKCandidate, native_mork
    import rebuilt_mork
    manifest_path = Path(manifest_path).resolve(strict=True)
    candidate = RebuiltMORKCandidate(manifest_path,
        expected_manifest_sha256=manifest_sha256, python_executable=profile['python'])
    pins = dict(candidate.manifest['files'])
    pins[str(manifest_path)] = manifest_sha256
    source = Path(__file__).resolve().parent
    helpers = [Path(native_mork.__file__).resolve(), Path(rebuilt_mork.__file__).resolve()]
    helpers += [native_mork.ROOT / relative for relative in native_mork.CHILD_FILE_HASHES]
    helpers += [source / name for name in
                ('mork_host.py', 'mork_supervise.py', 'mork_v2.py', 'fresh_supervise.py')]
    for path in helpers:
        path = str(path.resolve(strict=True))
        digest = sha(path)
        if path in pins and pins[path] != digest:
            raise ValueError('Conflicting MORK helper pin: '+path)
        pins[path] = digest
    for path, expected in pins.items():
        if not Path(path).is_absolute():
            raise ValueError('MORK closure paths must be absolute')
        if path in profile['files'] and profile['files'][path] != expected:
            raise ValueError('Conflicting MORK source pin: '+path)
    profile['files'].update(pins)
    profile['mork_memory'] = {'manifest':str(manifest_path),
                              'manifest_sha256':manifest_sha256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbolic-profile', type=Path, required=True)
    parser.add_argument('--infer', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ecan-profile', type=Path)
    parser.add_argument('--nars-manifest', type=Path)
    parser.add_argument('--nars-admission')
    parser.add_argument('--nars-evidence-root', type=Path)
    parser.add_argument('--mork-manifest', type=Path)
    parser.add_argument('--mork-manifest-sha256')
    parser.add_argument('--context-projection',choices=['extractive_v1'])
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refuse to replace a qualification profile')
    profile = json.loads(args.symbolic_profile.read_text())
    if args.ecan_profile:
        fragment = json.loads(args.ecan_profile.read_text())
        profile['ecan'] = fragment['ecan']
        for path, expected in fragment['files'].items():
            if path in profile['files'] and profile['files'][path] != expected:
                raise ValueError('Conflicting source pin: '+path)
            profile['files'][path] = expected
    for path, expected in profile['files'].items():
        if sha(path) != expected:
            raise ValueError('Symbolic profile changed: '+path)
    profile.update(kind='roko-fresh-host-v1', infer=str(args.infer.resolve(strict=True)),
                   model=str(args.model.resolve(strict=True)),
                   qualification='Prepared; requires actual native conversation probe')
    if args.context_projection:
        import os
        source=Path(__file__).resolve().parent
        stamp=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
        command=[profile['python'],'-B',str(source/'fresh_supervise.py'),
            '--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds','10','--',
            profile['infer'],'--model',profile['model'],'--count-tokens']
        result=subprocess.run(command,input=b'Qualification tokenizer probe',capture_output=True,
            start_new_session=True,timeout=20,check=True)
        counted=json.loads(result.stdout)
        if (type(counted) is not dict or set(counted)!={'input_tokens'} or
                type(counted['input_tokens']) is not int or counted['input_tokens']<1 or
                b'descendants_cleaned=1' not in result.stderr or b'ROKO_GENERATION ' in result.stderr):
            raise ValueError('Native token counting capability not qualified')
        profile['context_projection']=args.context_projection
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
    if any((args.nars_manifest,args.nars_admission,args.nars_evidence_root)):
        if not all((args.nars_manifest,args.nars_admission,args.nars_evidence_root)):
            raise ValueError('All three NARS qualification options are required')
        import cognition  # installs the fixed repository namespace for this script
        from components.nars_hyperon.source.runtime import verify
        manifest_path=args.nars_manifest.resolve(strict=True)
        manifest=json.loads(manifest_path.read_bytes())
        verify(manifest,args.nars_admission)
        if sha(manifest_path)!=args.nars_admission:
            raise ValueError('NARS manifest must use canonical bytes')
        profile['files'].update(manifest['files'])
        profile['files'][str(manifest_path)]=sha(manifest_path)
        profile['nars_cognition']={'manifest':str(manifest_path),'admission':args.nars_admission,
            'evidence_root':str(args.nars_evidence_root.absolute())}
    add_mork_profile(profile,args.mork_manifest,args.mork_manifest_sha256)
    from fresh import load_profile
    # Write once; verification errors remain explicit evidence, not rewritten locks.
    with args.output.open('x') as stream:
        json.dump(profile,stream,indent=2)
        stream.write('\n')
    load_profile(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
