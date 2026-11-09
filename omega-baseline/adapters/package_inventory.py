"""Read-only Debian archive awareness, independent of Nix and host dpkg state."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'package': r'[a-z0-9][a-z0-9+.-]{0,199}',
    'version': r'[A-Za-z0-9][A-Za-z0-9.+:~_-]{0,199}',
    'architecture': r'[a-z0-9][a-z0-9-]{0,49}',
    'sha256': r'[a-f0-9]{64}',
}

def load_inventory(root=ROOT, verify_archives=False):
    root = Path(root).resolve()
    path = root / 'boot/tooling-packages.lock.json'
    raw = path.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Inventory exceeds size limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    doc = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(doc, dict) or not isinstance(doc.get('packages'), list):
        raise ValueError('Expected package inventory object')
    rows = doc['packages']
    if not 1 <= len(rows) <= 10000:
        raise ValueError('Invalid package inventory count')
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Invalid package record')
        clean = {}
        for key, pattern in PATTERNS.items():
            value = row.get(key)
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError('Invalid ' + key)
            clean[key] = value
        identity = (clean['package'], clean['architecture'])
        if identity in seen: raise ValueError('Duplicate package/architecture')
        seen.add(identity)
        name = row.get('file')
        if not isinstance(name, str): raise ValueError('Invalid archive path')
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or str(rel) != name or not name.startswith('boot/tooling/archives/') or rel.suffix != '.deb':
            raise ValueError('Archive path must be confined to workspace archive directory')
        archive = root / rel
        if not archive.resolve().is_relative_to(root / 'boot/tooling/archives') or archive.is_symlink():
            raise ValueError('Archive path escapes archive directory or is a symlink')
        size = row.get('bytes')
        if type(size) is not int or size <= 0: raise ValueError('Invalid archive size')
        clean.update(file=name, bytes=size)
        if verify_archives:
            if not archive.is_file() or archive.stat().st_size != size:
                raise ValueError('Missing or size-mismatched archive: ' + name)
            with archive.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != clean['sha256']: raise ValueError('Archive checksum mismatch: ' + name)
        result.append(clean)
    return {'packages': sorted(result, key=lambda r:(r['package'],r['architecture'])),
            'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'archives_verified': verify_archives, 'host_dpkg_observed': False,
            'signed_metadata_reverified': False, 'package_changes_executed': 0}

def atoms(inventory):
    # Revalidate every emitted token, even when passed an in-memory object.
    lines = []
    for row in inventory['packages']:
        for key, pattern in PATTERNS.items():
            if not isinstance(row.get(key), str) or not re.fullmatch(pattern, row[key]):
                raise ValueError('Unsafe atom field: ' + key)
        lines.append('(workspace-deb ' + ' '.join(json.dumps(row[k]) for k in PATTERNS) + ')')
    return '\n'.join(lines) + '\n'
