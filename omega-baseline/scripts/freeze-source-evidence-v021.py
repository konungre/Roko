#!/usr/bin/env python3
"""Prepare selected immutable source snapshots and the 0.21 inventory.

Run `--snapshots` once, review/add the milestone and test receipts, then run
`--inventory`. The packager accepts only that exact inventory. This does not
prepare a runnable guest or copy any native capsule/runtime/model/disk payload.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'results/milestone-v021'
SNAPS = ROOT / 'boot/artifacts/recipes-0.21'
SPEC = importlib.util.spec_from_file_location('pkg', ROOT / 'scripts/package-source-evidence.py')
pkg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pkg)

SOURCE_SUFFIXES = {'.py', '.pl', '.metta', '.sh', '.c', '.h', '.cpp', '.md', '.txt',
                   '.json', '.lock', '.sha256', '.toml', '.xml', '.desktop', '.ron',
                   '.conf', '.rules', '.patch', '.diff', '.yaml', '.yml', '.cmake'}
SOURCE_NAMES = {'LICENSE', 'COPYING', 'CMakeLists.txt', 'SHA256SUMS', 'roko-corner',
                'env.sh', 'session-init', 'BusyBox-copyright', 'glibc-copyright',
                'GPL-2', 'LGPL-2.1', 'PyYAML-LICENSE', 'cosmic-source-LICENSE'}
BOOT_DIRS = '''basilisk-avatar-guest basilisk-guest cognitive-capsule-guest
cognitive-filesystem-guest companion-controls-guest companion-model-guest
companion-model-guest-compact companion-model-guest-cache128 cosmic-dock-overlay
cosmic-files-portals-guest cosmic-guest cosmic-persistent-guest cosmic-session-guest
desktop-filesystem-guest disk-root-guest files-delta-guest filesystem-guest
granite-guest granite-guest-representative granite-guest-representative-gate
granite-host-companion granite-model-guest granite-model-guest-extended
granite-model-guest-fourcore granite-model-guest-recovery granite-portable
granite-raw-block portal-input-guest roko-corner-guest test-delta-root userland
licenses'''.split()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_source(path):
    return path.suffix in SOURCE_SUFFIXES or path.name in SOURCE_NAMES or path.name.endswith('-LICENSE')


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def snapshots():
    if SNAPS.exists():
        raise FileExistsError('Snapshot directory already exists; do not overwrite')
    origins = []

    def copy(source, target, pin=None):
        data = source.read_bytes()
        assert not source.is_symlink() and not data.startswith(pkg.FORBIDDEN_MAGICS), source
        if pin:
            assert len(data) == pin['bytes'] and pkg.digest(data) == pin['sha256'], source
        dest = SNAPS / target
        write_new(dest, data)
        origins.append({'path': str(dest.relative_to(ROOT)), 'source': str(source),
                        'bytes': len(data), 'sha256': pkg.digest(data),
                        'checked_against_tested_manifest': bool(pin)})

    stages = {
        'companion-tested': 'build-src/companion-model-guest/stage-v2-compact',
        'granite-fourcore-tested': 'build-src/granite-model-guest-stage/candidate-v4-fourcore',
        'granite-representative-tested': 'build-src/granite-model-guest-stage/candidate-v5-two-fixed-cases',
        'cognitive-capsule-tested': 'build-src/cognitive-capsule-guest/stage-v4',
    }
    for label, name in stages.items():
        stage = ROOT / name
        manifest = json.loads((stage / 'manifest.json').read_text())
        copy(stage / 'manifest.json', Path(label) / 'manifest.json')
        for relative, pin in manifest['files'].items():
            rel = Path(relative)
            if label.startswith('granite-'):
                source = stage / 'roko' / rel
            else:
                source = stage / rel
            # Only exact source and selected authored artwork. Never runtime libs.
            if label == 'cognitive-capsule-tested' and not relative.startswith(
                    ('capsule/bridge/', 'capsule/petta/', 'capsule/omega/', 'roko/', 'licenses/')):
                continue
            if is_source(rel) or relative in {
                    'corner/usr/share/roko/corner/assets/character.png',
                    'corner/usr/share/roko/corner/assets/corner.png'}:
                copy(source, Path(label) / rel, pin)
        for diff in sorted(stage.glob('*.diff')):
            copy(diff, Path(label) / diff.name)
    harness = ROOT / 'build-src/cognitive-capsule-guest/harness-v3'
    for file in sorted(harness.iterdir()):
        if file.is_file() and is_source(file):
            copy(file, Path('cognitive-harness-tested') / file.name)
    corner = ROOT.parent / 'roko-corner-prototype-v2'
    for file in sorted(corner.rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts and is_source(file):
            copy(file, Path('corner-v2-source') / file.relative_to(corner))
    for name in ('assets/character.png', 'assets/corner.png'):
        copy(corner / name, Path('corner-v2-source') / name)
    write_new(SNAPS / 'origin-map.json', (json.dumps({'scope': 'Exact selected source/art snapshots only; native binaries and private inputs omitted.', 'files': origins}, indent=2)+'\n').encode())
    print(json.dumps({'snapshot_files': len(origins), 'bytes': sum(r['bytes'] for r in origins)}, indent=2))


def inventory():
    selected = {}

    def add(path, category):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        name = str(path.relative_to(ROOT))
        pkg.checked_path(ROOT, name)
        selected[name] = category

    def tree(name, category, suffixes=None):
        for path in sorted((ROOT / name).rglob('*')):
            if not path.is_file() or path.is_symlink() or set(path.relative_to(ROOT).parts) & pkg.FORBIDDEN_PARTS:
                continue
            if suffixes is not None and path.suffix not in suffixes:
                continue
            if suffixes is None and not is_source(path) and path.suffix != '.png':
                continue
            add(path, category)

    for path in sorted(ROOT.iterdir()):
        if path.is_file() and is_source(path):
            add(path, 'project-source-and-scope')
    # Exact already locked upstream source set, no automatic vendor traversal.
    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    for repo in lock['repositories']:
        for name, expected in repo['files'].items():
            path = ROOT / repo['path'] / name
            assert sha(path) == expected, path
            add(path, 'locked-upstream-source')
    for name in ('adapters', 'components', 'scripts', 'os-overlay', 'desktop'):
        tree(name, 'authored-source')
    add('bin/roko', 'authored-source')
    for path in sorted((ROOT / 'integration').iterdir()):
        if path.is_file() and is_source(path) and path.name != 'GUEST_COGNITIVE_GATE_PLAN.md':
            add(path, 'historical-integration-source')
    for path in sorted((ROOT / 'tests').glob('test_*.py')):
        if path.name != 'test_cognitive_model_context.py':
            add(path, 'source-test')
    for path in sorted((ROOT / 'boot').iterdir()):
        if path.is_file() and is_source(path):
            add(path, 'boot-recipe-lock-or-notice')
    for name in BOOT_DIRS:
        tree('boot/' + name, 'boot-recipe-lock-or-notice')
    tree('boot/artifacts/recipes-0.21', 'selected-tested-source-snapshot')
    # Reuse only the old packager's explicit authored stage receipts, not its walk.
    syntax = ast.parse((ROOT / 'scripts/package-milestone.py').read_text())
    node = next(n.value for n in syntax.body if isinstance(n, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'receipts' for t in n.targets))
    receipts = ast.literal_eval(node)
    for stage, names in receipts.items():
        for name in names:
            add('build-src/' + stage + '/' + name, 'selected-build-recipe-or-receipt')
    for stage in ('cosmic-files-portals-stage', 'files-corner-source-plan'):
        for path in sorted((ROOT / 'build-src' / stage).iterdir()):
            if path.is_file() and is_source(path):
                add(path, 'selected-build-recipe-or-receipt')
    for name in ('build-src/granite-guest-stage/source-v2/manifest.json',
                 'build-src/granite-portable-stage/source-v2/manifest.json',
                 'build-src/granite-portable-stage/source-v2/provider.diff',
                 'results/package-v020.json'):
        add(name, 'historical-manifest-or-receipt')
    for name in ('results/granite-model-guest', 'results/cognitive-capsule-guest',
                 'results/cognitive-capsule-preparation', 'results/reviewed-milestones',
                 'results/companion-model-guest', 'results/disk-root-guest'):
        tree(name, 'selected-runtime-evidence', {'.md', '.json', '.txt', '.diff', '.png'})
    # Preserve selected raw images and original scoped logs, without all capture trees.
    for name in ('results/companion-model-guest/attempt-3/answer-first.ppm',
                 'results/companion-model-guest/attempt-3/care-during-native.ppm',
                 'results/disk-root-guest/actual-terminal-root-check.ppm',
                 'results/roko-corner-guest/serial.txt',
                 'results/files-delta-guest-attempts/20261107T222834Z-nl9psaha/evidence/serial.txt'):
        add(name, 'selected-raw-evidence')
    for path in sorted((ROOT / 'results/reviewed-milestones').rglob('*.ppm')):
        add(path, 'selected-raw-evidence')
    files_review = json.loads((ROOT / 'results/reviewed-milestones/files-operations-v1/files-operation-review.json').read_text())
    for row in files_review['screenshots'].values():
        add('results/files-delta-guest-attempts/20261107T222834Z-nl9psaha/evidence/' + Path(row['raw']).name, 'selected-raw-evidence')
    corner_review = json.loads((ROOT / 'results/reviewed-milestones/corner-follow-v1/interaction-review.json').read_text())
    for name in corner_review['captures']:
        add('results/roko-corner-guest/' + name + '.ppm', 'selected-raw-evidence')
    for path in sorted((ROOT / 'results/screenshots').glob('*.png')):
        if path.name.startswith(('roko-files-', 'roko-corner-', 'roko-chooser-', 'roko-controls-', 'roko-portal-input-')):
            add(path, 'reviewed-screenshot')
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.name not in {'inventory.json', 'preservation-after.json'}:
            add(path, 'packaging-validation')
    rows = []
    for name, category in sorted(selected.items()):
        path = ROOT / name
        mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        row = {'path': name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'mode': mode, 'category': category}
        pkg.checked_bytes(ROOT, row)
        rows.append(row)
    report = {
        'schema': 1, 'version': '0.21.0', 'scope': 'Selected source/recipes/tests and exact evidence only; not a runnable or complete corresponding-source distribution.',
        'excluded': ['model weights', 'private runtime/capsule binaries', 'disk images and user state',
                     'cache/toolchain/build trees', 'credentials and git pointers', 'internal notes',
                     'upstream MORK/ECAN trees', 'unfinished joint symbolic/Granite/ECAN candidate'],
        'inventory_self_hash_note': 'This inventory is the only ZIP member not listed in files; its SHA-256 is in the external final package receipt.',
        'files': rows,
    }
    write_new(HERE / 'inventory.json', (json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'inventory_files': len(rows), 'uncompressed_bytes': sum(r['bytes'] for r in rows)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', action='store_true')
    parser.add_argument('--inventory', action='store_true')
    args = parser.parse_args()
    if args.snapshots:
        snapshots()
    if args.inventory:
        inventory()
