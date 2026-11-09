"""Validate native fact queries against a fresh, read-only manifest snapshot."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adapters'))
from package_inventory import load_inventory
_inventory = None

def initialize():
    global _inventory
    _inventory = load_inventory()
    return len(_inventory['packages'])

def matches(name, version, architecture, sha256):
    if _inventory is None: raise RuntimeError('Inventory is not initialized')
    return any((r['package'],r['version'],r['architecture'],r['sha256']) ==
               (name,version,architecture,sha256) for r in _inventory['packages'])
