#!/usr/bin/env python3
"""Offline, deterministic release packing. Never installs or selects a boot slot.

Locks are reviewed local inputs, not signatures or proof of upstream authenticity.
Flat asset names and descriptor-relative opens prevent symlink traversal.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile

MAX_ASSET = 64 * 1024**3
ROLES = {"kernel", "initramfs", "rootfs", "model", "firmware"}
REQUIRED = {"kernel", "initramfs", "rootfs"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_lock(path):
    with open(path, "rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Lock exceeds 1 MiB")
    lock = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(lock, dict) or set(lock) != {"schema", "architecture", "release", "assets"}:
        raise ValueError("Invalid lock fields")
    if lock["schema"] != "roko-release-v1" or lock["architecture"] != "x86_64":
        raise ValueError("Unsupported schema or architecture")
    if not isinstance(lock["release"], str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", lock["release"]):
        raise ValueError("Invalid release ID")
    assets = lock["assets"]
    if not isinstance(assets, list) or not 3 <= len(assets) <= 128:
        raise ValueError("Expected 3..128 assets")
    names, roles = set(), []
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"name", "role", "bytes", "sha256"}:
            raise ValueError("Invalid asset fields")
        name = asset["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", name) or name in names:
            raise ValueError("Invalid or duplicate flat asset name")
        if not isinstance(asset["role"], str) or asset["role"] not in ROLES:
            raise ValueError("Unknown role")
        if type(asset["bytes"]) is not int or not 0 < asset["bytes"] <= MAX_ASSET:
            raise ValueError("Invalid asset size")
        if not isinstance(asset["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
            raise ValueError("Invalid SHA256")
        names.add(name)
        roles.append(asset["role"])
    if any(roles.count(role) != 1 for role in REQUIRED):
        raise ValueError("Exactly one kernel, initramfs and rootfs required")
    return {**lock, "assets": sorted(assets, key=lambda item: item["name"])}


class CheckedReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, count):
        data = self.stream.read(count)
        self.digest.update(data)
        return data


def header(name, size):
    item = tarfile.TarInfo(name)
    item.size = size
    item.mode = 0o444
    item.mtime = 0
    item.uid = item.gid = 0
    return item


def pack(lock_path, assets_dir, output):
    lock = load_lock(lock_path)
    directory = Path(assets_dir)
    if directory != directory.resolve():
        raise ValueError("Assets directory must be absolute, canonical and symlink-free")
    output = Path(output)
    # Output parent is a trusted operator-owned build directory.
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".roko-release-", dir=output.parent, delete=False) as destination:
            temporary = Path(destination.name)
            with tarfile.open(fileobj=destination, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                raw = canonical(lock)
                archive.addfile(header("release.json", len(raw)), io.BytesIO(raw))
                for asset in lock["assets"]:
                    fd = os.open(asset["name"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
                    with os.fdopen(fd, "rb") as source:
                        before = os.fstat(source.fileno())
                        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != asset["bytes"]:
                            raise ValueError("Asset must be singly-linked regular file of locked size")
                        checked = CheckedReader(source)
                        archive.addfile(header("assets/" + asset["name"], before.st_size), checked)
                        after = os.fstat(source.fileno())
                        if source.read(1) or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                            raise ValueError("Asset changed while packing")
                        if checked.digest.hexdigest() != asset["sha256"]:
                            raise ValueError("Digest mismatch: " + asset["name"])
            destination.flush()
            os.fsync(destination.fileno())
        # Hard-link publication is exclusive: no existing checkpoint is replaced.
        os.link(temporary, output)
        parent_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        os.close(directory_fd)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with output.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"release": lock["release"], "sha256": digest.hexdigest(), "bytes": output.stat().st_size,
            "boot_tested": False, "hardware_tested": False, "signature_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("assets", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(pack(args.lock, args.assets, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
