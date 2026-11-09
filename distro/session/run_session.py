#!/usr/bin/env python3
"""Two-phase COSMIC/state qualification, one explicit phase per invocation.

Read-only preserved ISO and new capsule; one private regular-file disk, no NIC.
Read-only model closure is present but inference is not requested by this gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import stat
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_probe import verify_runtime
from state_image import open_image
from session_evidence import validate

ISO_SHA = "a3cc3cb741f50b2bd1846080bb1995067f22a27fc79091fc3e63ef4162c31253"


def fd_sha(fd):
    digest = hashlib.sha256()
    offset = 0
    while True:
        block = os.pread(fd, 1024 * 1024, offset)
        if not block: break
        digest.update(block); offset += len(block)
    return digest.hexdigest()


def available():
    rows = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    return int(rows["MemAvailable"].split()[0]) * 1024


class QMP:
    def __init__(self, proc):
        self.proc = proc
        self.buffer = bytearray()
        self.identifier = 0
        if "QMP" not in self.receive(): raise ValueError("Missing QMP greeting")
        self.call("qmp_capabilities")

    def receive(self):
        end = time.monotonic() + 5
        while b"\n" not in self.buffer:
            if time.monotonic() > end: raise TimeoutError("QMP timeout")
            if not select.select([self.proc.stdout], [], [], .2)[0]: continue
            block = os.read(self.proc.stdout.fileno(), 65536)
            if not block: raise EOFError("QMP closed")
            self.buffer.extend(block)
            if len(self.buffer) > 1024 * 1024: raise ValueError("QMP output bound")
        raw, _, self.buffer = self.buffer.partition(b"\n")
        return json.loads(raw)

    def call(self, execute, arguments=None):
        self.identifier += 1
        packet = {"execute": execute, "id": self.identifier}
        if arguments is not None: packet["arguments"] = arguments
        self.proc.stdin.write(json.dumps(packet).encode() + b"\n"); self.proc.stdin.flush()
        for _ in range(32):
            row = self.receive()
            if row.get("id") == self.identifier:
                if "error" in row: raise ValueError("QMP command failed: " + str(row["error"]))
                return row
        raise ValueError("QMP response event bound")


def run(capsule, runtime, runtime_lock, iso, image_dir, output, phase):
    if phase not in ("write", "read"): raise ValueError("Explicit write/read phase required")
    capsule, runtime, iso, output = map(Path, (capsule, runtime, iso, output))
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    verification = verify_runtime(runtime, runtime_lock)
    derivation = json.loads((capsule / "derivation.json").read_text())
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in Path(__file__).parent.glob("*.py")}
    fds = {}
    proc = None
    started = None
    report = {"schema": "roko-foundation-session-v1", "phase": phase,
              "host_source_sha256": source_hashes, "runtime": verification, "guest_memory_mib": 3072, "passed": False, "visual_review_required": True, "model_inference_tested": False,
              "host_disks": False, "private_state_disk": True, "network": False,
              "stop_mode": "controlled host stop after durable user checkpoint; no guest clean-unmount claim"}
    try:
        for name, path, expected in (("iso", iso, ISO_SHA), ("initrd", capsule / "session.cpio.gz", derivation["sha256"])):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            fds[name] = fd
            if not stat.S_ISREG(os.fstat(fd).st_mode) or fd_sha(fd) != expected:
                raise ValueError("Immutable input mismatch: " + name)
            report[name + "_sha256"] = expected
        fds["state"] = open_image(image_dir)
        report["state_before_sha256"] = fd_sha(fds["state"])
        if available() < 6 * 1024**3: raise ValueError("Need 6 GiB available before 3 GiB desktop-only VM")
        if shutil.disk_usage(output.parent).free < 4 * 1024**3 + 64 * 1024**2:
            raise ValueError("Need 4 GiB free plus bounded evidence reservation")
        output.mkdir(mode=0o700)
        fds["serial"] = os.open(output / "serial.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        library = runtime / "usr/lib/x86_64-linux-gnu"
        kernel = runtime / "boot/vmlinuz-6.12.115+deb13.1-amd64"
        def descriptor(name): return f"/proc/self/fd/{fds[name]}"
        command = [str(library / "ld-linux-x86-64.so.2"), "--inhibit-cache", "--library-path", str(library),
            str(runtime / "usr/bin/qemu-system-x86_64"), "-L", str(runtime / "usr/share/qemu"),
            "-bios", str(runtime / "usr/share/seabios/bios-256k.bin"), "-no-user-config", "-nodefaults",
            "-machine", "q35", "-accel", "tcg,thread=multi,tb-size=128", "-cpu", "max",
            "-m", "3072", "-smp", "4", "-display", "none", "-monitor", "none", "-nic", "none", "-no-reboot",
            "-qmp", "stdio", "-serial", "file:" + descriptor("serial"), "-kernel", str(kernel), "-initrd", descriptor("initrd"),
            "-append", "console=tty0 console=ttyS0,115200 rdinit=/init panic=1 roko.probe=unprivileged005 roko.foundation-state=" + phase,
            "-device", "virtio-vga,romfile=" + str(runtime / "usr/share/seabios/vgabios-virtio.bin"),
            "-device", "virtio-keyboard-pci", "-device", "virtio-tablet-pci", "-device", "ich9-ahci,id=liveahci",
            "-blockdev", json.dumps({"driver":"file","filename":descriptor("iso"),"node-name":"mediafile","read-only":True}),
            "-blockdev", json.dumps({"driver":"raw","file":"mediafile","node-name":"media","read-only":True}),
            "-device", "ide-cd,bus=liveahci.0,drive=media",
            "-blockdev", json.dumps({"driver":"file","filename":descriptor("state"),"node-name":"statefile","cache":{"direct":False,"no-flush":False}}),
            "-blockdev", json.dumps({"driver":"raw","file":"statefile","node-name":"state"}),
            "-device", "virtio-blk-pci,drive=state,serial=ROKO_STATE_TEST"]
        report["command"] = command
        (output / "admission.json").write_text(json.dumps(report, indent=2) + "\n")
        started = time.monotonic()
        with (output / "qemu-stderr.txt").open("xb") as errors:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                pass_fds=tuple(fds.values()), env={"PATH":"/usr/bin:/bin","LANG":"C","QEMU_MODULE_DIR":str(library / "qemu")})
            qmp = QMP(proc)
            reason = "timeout"
            ready_at = None
            while time.monotonic() - started < 390:
                if proc.poll() is not None: reason = "unexpected_exit"; break
                if (output / "serial.txt").stat().st_size > 2 * 1024**2:
                    reason = "output_limit"; break
                if available() < 2 * 1024**3: reason = "host_memory_floor"; break
                rss = next((int(line.split()[1])*1024 for line in Path(f"/proc/{proc.pid}/status").read_text().splitlines() if line.startswith("VmRSS:")), 0)
                if rss > 4 * 1024**3: reason = "qemu_memory_limit"; break
                log = (output / "serial.txt").read_text(errors="replace")
                if any(marker in log for marker in ("ROKO_UNPRIVILEGED_PREPARE_FAILED", "ROKO_START_FAILED", "ROKO_LIVE_BOOT_FAILED", "Kernel panic")):
                    reason = "guest_failure"; break
                if "ROKO_DESKTOP_READY uid=1000 inference=not-started" in log and "ROKO_FOUNDATION_STATE_VERIFIED " + phase + " uid=1000 revision=1" in log:
                    report.update(validate(log, phase))
                    if ready_at is None: ready_at = time.monotonic()
                    if time.monotonic() - ready_at < 30:
                        time.sleep(.5)
                        continue
                    qmp.call("screendump", {"filename":str((output / "desktop.ppm").resolve())})
                    reason = "desktop_and_state_ready"; break
                time.sleep(.5)
            report["stop_reason"] = reason
            qmp.call("quit")
            proc.wait(timeout=10)
            report["returncode"] = proc.returncode
            report["passed"] = reason == "desktop_and_state_ready" and proc.returncode == 0
    except BaseException as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
            proc.stdin.close(); proc.stdout.close()
            report["child_reaped"] = proc.poll() is not None
        if "state" in fds:
            os.fsync(fds["state"])
            report["state_after_sha256"] = fd_sha(fds["state"])
        for fd in fds.values(): os.close(fd)
        if started is not None: report["elapsed_seconds"] = time.monotonic() - started
        if output.is_dir(): (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("capsule", "runtime", "runtime_lock", "iso", "image_dir", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("phase", choices=("write", "read"))
    args = parser.parse_args()
    result = run(**vars(args))
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["passed"])
