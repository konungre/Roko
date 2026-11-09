"""Pin optional native Motto transport; runtime qualification remains separate."""
import argparse
import hashlib
import json
from pathlib import Path
from fresh import load_profile
from motto import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--guard-manifest', required=True)
    parser.add_argument('--evidence-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    profile = load_profile(args.profile)
    manifest_path = Path(args.guard_manifest).resolve(strict=True)
    manifest = json.loads(manifest_path.read_bytes())
    admission = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    from components.nars_hyperon.source.runtime import verify
    verify(manifest, admission)
    pins = dict(manifest['files'])
    pins[str(manifest_path)] = admission
    paths = [p for p in ROOT.rglob('*') if p.is_file()] + [Path(manifest['python'])]
    pins.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    for name, digest in pins.items():
        if name in profile['files'] and profile['files'][name] != digest:
            raise ValueError('Conflicting Motto source pin')
    profile['files'].update(pins)
    profile['motto_transport'] = {'python': manifest['python'], 'guard_manifest': str(manifest_path),
        'guard_admission': admission, 'evidence_root': str(Path(args.evidence_root).absolute())}
    with open(args.output, 'x') as stream:
        json.dump(profile, stream, sort_keys=True)
    load_profile(args.output)


if __name__ == '__main__':
    main()
