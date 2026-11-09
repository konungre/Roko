#!/usr/bin/env python3
"""Explicit bounded TCG probe run using an operator-reviewed local runtime lock.

No downloads, disks, networking, KVM, GUI, model or system service changes.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import selectors
import stat
import subprocess
import time
from probe_gate import sha, serial_evidence


def verify_runtime(root, lock_path):
    root = Path(root)
    if root != root.resolve():
        raise ValueError("Runtime root must be canonical")
    lock = json.loads(Path(lock_path).read_text())
    files = lock["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("Missing runtime inventory")
    for name, record in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError("Unsafe inventory path")
        target = root / name
        if target.parent.resolve() != target.parent:
            raise ValueError("Symlinked parent in inventory")
        info = target.lstat()
        if record["kind"] == "symlink":
            if not stat.S_ISLNK(info.st_mode) or os.readlink(target) != record["target"]:
                raise ValueError("Symlink mismatch: " + name)
        elif record["kind"] == "file":
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != record["mode"] or sha(target) != record["sha256"]:
                raise ValueError("File mismatch: " + name)
        else:
            raise ValueError("Unknown inventory kind")
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_symlink() or not path.is_dir()}
    if actual != set(files):
        raise ValueError("Runtime contains missing or unlisted files")
    return {"entries_verified": len(files), "lock_sha256": sha(Path(lock_path))}


def run(probe, runtime, lock, output):
    probe, runtime, output = Path(probe).resolve(), Path(runtime), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    verification = verify_runtime(runtime, lock)
    manifest = json.loads((probe / "manifest.json").read_text())
    for name, field in (("init", "init_sha256"), ("initramfs.cpio.gz", "initramfs_sha256")):
        if sha(probe / name) != manifest[field]:
            raise ValueError("Probe changed")
    kernels = list((runtime / "boot").glob("vmlinuz-*"))
    if len(kernels) != 1:
        raise ValueError("Expected one pinned kernel")
    library = runtime / "usr/lib/x86_64-linux-gnu"
    command = [str(library / "ld-linux-x86-64.so.2"), "--library-path",
        str(library) + ":" + str(runtime / "lib/x86_64-linux-gnu"),
        str(runtime / "usr/bin/qemu-system-x86_64"), "-L", str(runtime / "usr/share/qemu"),
        "-bios", str(runtime / "usr/share/seabios/bios-256k.bin"),
        "-no-user-config", "-nodefaults", "-machine", "q35,accel=tcg",
        "-m", "256", "-smp", "1", "-display", "none", "-monitor", "none",
        "-serial", "stdio", "-nic", "none", "-no-reboot", "-kernel", str(kernels[0]),
        "-initrd", str(probe / "initramfs.cpio.gz"),
        "-append", "console=ttyS0 rdinit=/init panic=1"]
    output.mkdir(mode=0o700)
    report = {"schema": "roko-foundation-vm-v1", "command": command,
              "runtime": verification, "kernel_sha256": sha(kernels[0]),
              "initramfs_sha256": manifest["initramfs_sha256"], "build_id": manifest["build_id"],
              "boot_tested": False, "boot_passed": False, "network": False, "host_disks": False,
              "scope": "Minimal PID1/non-root probe only; no COSMIC, model or persistence"}
    (output / "admission.json").write_text(json.dumps(report, indent=2) + "\n")
    started = time.monotonic()
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "QEMU_MODULE_DIR": str(library / "qemu")})
    data = bytearray()
    stop = "eof"
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                if time.monotonic() - started > 60:
                    stop = "timeout"; break
                if not selector.select(0.25):
                    continue
                block = os.read(proc.stdout.fileno(), 65536)
                if not block:
                    break
                data.extend(block)
                if len(data) > 2 * 1024 * 1024:
                    stop = "output_limit"; break
        if stop != "eof" and proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stop = "kill_after_wait_timeout"
            proc.kill(); proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait(timeout=5)
        proc.stdout.close()
    (output / "serial.txt").write_bytes(data)
    evidence = serial_evidence(data.decode(errors="replace"), manifest["build_id"], proc.returncode)
    report.update(evidence)
    report.update({"boot_tested": True, "boot_passed": stop == "eof" and evidence["serial_contract_passed"],
        "returncode": proc.returncode, "stop_reason": stop, "elapsed_seconds": time.monotonic() - started,
        "serial_sha256": sha(output / "serial.txt"), "child_reaped": proc.poll() is not None})
    # This controller measured its own artifact binding and child exit, unlike a supplied log.
    report["native_execution_independently_established"] = report["boot_passed"]
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("probe", "runtime", "lock", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = run(args.probe, args.runtime, args.lock, args.output)
    print(json.dumps(report, indent=2))
    return 0 if report["boot_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
