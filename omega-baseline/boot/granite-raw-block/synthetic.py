"""Deterministic inert non-sector-aligned transport fixture, not model weights."""
import hashlib
from raw_transport import TRANSPORT, capacity

LENGTH = 1024 * 1024 + 352


def payload():
    # Public deterministic bytes with no MBR/GPT signature or real model header.
    block = hashlib.sha256(b'roko inert raw transport fixture v1').digest()
    return (block * ((LENGTH + len(block) - 1) // len(block)))[:LENGTH]


def specification():
    data = payload()
    return {'transport': TRANSPORT, 'serial': 'roko-raw-synthetic', 'source_bytes': len(data),
            'capacity_bytes': capacity(len(data)), 'sha256': hashlib.sha256(data).hexdigest(),
            'zero_tail_bytes': capacity(len(data)) - len(data), 'logical_block_size': 512,
            'status': 'synthetic-transport-probe-only'}
