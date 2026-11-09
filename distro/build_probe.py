#!/usr/bin/env python3
"""Compile a guest-only boot probe using inherited deterministic newc helpers.

Output is an exclusive new directory. No VM, network, disk or host install.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "omega-baseline/boot/build.py"
SPEC = importlib.util.spec_from_file_location("roko_baseline_build", BASELINE)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)
PROFILE = {"schema": "roko-foundation-probe-v1", "architecture": "x86_64",
           "desktop": False, "model": False, "persistent_state": False,
           "network": False, "host_disks": False, "probe_uid": 1000}
FLAGS = ["-nostdlib", "-static", "-Os", "-s", "-fno-pie", "-no-pie",
         "-fno-stack-protector", "-fno-builtin", "-mno-sse", "-mno-mmx",
         "-fno-asynchronous-unwind-tables", "-fno-ident", "-Wl,--build-id=none"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(output, compiler="gcc"):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    source = (HERE / "boot_probe.c").read_bytes()
    profile = (json.dumps(PROFILE, sort_keys=True, separators=(",", ":")) + "\n").encode()
    build_id = digest(source + profile + json.dumps(FLAGS).encode())
    executable = shutil.which(compiler)
    if executable is None:
        raise ValueError("Compiler unavailable")
    with tempfile.TemporaryDirectory(prefix=".roko-probe-", dir=output.parent) as temporary:
        stage = Path(temporary)
        # Compile a private snapshot, not a source pathname that can change mid-build.
        (stage / "init.c").write_bytes(source)
        subprocess.run([executable, *FLAGS, '-DROKO_BUILD_ID="' + build_id + '"',
                        str(stage / "init.c"), "-o", str(stage / "init")], check=True, timeout=60)
        binary = (stage / "init").read_bytes()
        baseline.check_elf(binary)
        records = [
            ("dev", b"", stat.S_IFDIR | 0o755, 0, 0),
            ("dev/console", b"", stat.S_IFCHR | 0o600, 5, 1),
            ("etc", b"", stat.S_IFDIR | 0o755, 0, 0),
            ("etc/roko-profile.json", profile, stat.S_IFREG | 0o444, 0, 0),
            ("init", binary, stat.S_IFREG | 0o755, 0, 0),
            ("proc", b"", stat.S_IFDIR | 0o755, 0, 0),
            ("sys", b"", stat.S_IFDIR | 0o755, 0, 0)]
        archive = b"".join(baseline.entry(name, data, mode, i, major, minor)
                           for i, (name, data, mode, major, minor) in enumerate(records, 1))
        archive += baseline.entry("TRAILER!!!", b"", 0, len(records) + 1)
        archive += b"\0" * (-len(archive) % 512)
        entries = baseline.inspect(archive)
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
            stream.write(archive)
        compressed = buffer.getvalue()
        report = {"schema": "roko-foundation-build-v1", "build_id": build_id,
                  "source_sha256": digest(source), "baseline_helper_sha256": digest(BASELINE.read_bytes()),
                  "compiler": subprocess.check_output([executable, "--version"], text=True).splitlines()[0],
                  "compiler_sha256": digest(Path(executable).read_bytes()), "flags": FLAGS,
                  "init_sha256": digest(binary), "initramfs_sha256": digest(compressed),
                  "entries": entries, "boot_tested": False, "nonroot_guest_tested": False,
                  "scope": "Compiled PID1 probe only; no COSMIC, model or persistence"}
        (stage / "initramfs.cpio.gz").write_bytes(compressed)
        (stage / "manifest.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        # Never replace an existing directory, including an empty checkpoint.
        output.mkdir(mode=0o700)
        try:
            for name in ("init", "initramfs.cpio.gz", "manifest.json"):
                os.link(stage / name, output / name)
                with (output / name).open("rb") as stream:
                    os.fsync(stream.fileno())
            for directory in (output, output.parent):
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except BaseException:
            # Keep an explicitly incomplete directory for inspection; no replacement.
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--compiler", default="gcc")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.compiler), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
