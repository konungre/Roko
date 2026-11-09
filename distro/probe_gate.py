#!/usr/bin/env python3
"""Read-only preflight for the compiled probe. Never executes QEMU."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def preflight(probe, assets_lock):
    blockers = []
    report = {"schema": "roko-foundation-preflight-v1", "boot_tested": False,
              "nonroot_guest_tested": False, "network": False, "host_disks": False,
              "runtime_closure_verified": False, "command": None, "blockers": blockers}
    paths = {}
    try:
        manifest = json.loads((Path(probe) / "manifest.json").read_text())
        if manifest["schema"] != "roko-foundation-build-v1" or not re.fullmatch("[0-9a-f]{64}", manifest["build_id"]):
            raise ValueError("Invalid build manifest")
        for name, field in (("init", "init_sha256"), ("initramfs.cpio.gz", "initramfs_sha256")):
            path = Path(probe) / name
            if path.is_symlink() or not path.is_file() or sha(path) != manifest[field]:
                raise ValueError("Probe artifact mismatch: " + name)
        report["build_id"] = manifest["build_id"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        blockers.append("probe: " + str(error))
    try:
        assets = json.loads(Path(assets_lock).read_text())
        for role in ("kernel", "qemu"):
            try:
                record = assets[role]
                if type(record) is not dict or set(record) != {"path", "sha256"}:
                    raise ValueError("Expected path and sha256")
                path = Path(record["path"])
                if not path.is_absolute() or not path.is_file() or path.is_symlink():
                    raise ValueError("Missing absolute regular file")
                if sha(path) != record["sha256"]:
                    raise ValueError("Pinned digest mismatch")
                paths[role] = str(path)
            except (OSError, ValueError, KeyError, TypeError) as error:
                blockers.append(role + ": " + str(error))
    except (OSError, ValueError, TypeError) as error:
        blockers.append("assets lock: " + str(error))
    if not blockers:
        report["command"] = [paths["qemu"], "-no-user-config", "-nodefaults",
            "-machine", "q35,accel=tcg", "-m", "256", "-smp", "1",
            "-display", "none", "-monitor", "none", "-serial", "stdio",
            "-nic", "none", "-no-reboot", "-kernel", paths["kernel"],
            "-initrd", str((Path(probe) / "initramfs.cpio.gz").resolve()),
            "-append", "console=ttyS0 rdinit=/init panic=1"]
    # Launcher hash alone does not verify the extracted QEMU/firmware libraries.
    blockers.append("Independent QEMU runtime/firmware closure verification required before execution")
    return report


def serial_evidence(log, build_id, returncode):
    """Check candidate serial evidence only; does not establish VM provenance."""
    if not re.fullmatch("[0-9a-f]{64}", build_id):
        raise ValueError("Invalid build ID")
    lines = log.replace("\r\n", "\n").splitlines()
    required = ["ROKO_FOUNDATION_ENTERED " + build_id,
                "ROKO_FOUNDATION_NONROOT uid=1000 gid=1000 groups=0 no_new_privs=1 regain_root=denied",
                "ROKO_FOUNDATION_COMPLETE " + build_id]
    positions = [lines.index(line) if lines.count(line) == 1 else -1 for line in required]
    passed = (returncode == 0 and all(i >= 0 for i in positions)
              and positions == sorted(positions)
              and not any("ROKO_FOUNDATION_FAILED" in line or "Kernel panic" in line for line in lines))
    return {"serial_contract_passed": passed, "native_execution_independently_established": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", type=Path)
    parser.add_argument("assets_lock", type=Path)
    args = parser.parse_args()
    result = preflight(args.probe, args.assets_lock)
    print(json.dumps(result, indent=2))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
