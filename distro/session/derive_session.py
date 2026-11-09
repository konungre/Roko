#!/usr/bin/env python3
"""Derive an opt-in state qualification capsule; never mutate the preserved input."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
BASE_SHA = "1b969946ea941564b91dd8438d4b870586675ab9a479bc06c99094f0de180116"
PREFIX = "payload/root/usr/lib/roko-unprivileged/"


def replace_once(raw, old, new):
    if raw.count(old.encode()) != 1:
        raise ValueError("Source anchor is not unique: " + old[:60])
    return raw.replace(old.encode(), new.encode())


def records(raw):
    offset, seen = 0, set()
    while True:
        header = raw[offset:offset+110]
        if len(header) != 110 or header[:6] != b"070701":
            raise ValueError("Invalid newc")
        fields = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        size, length = fields[6], fields[11]
        if not 1 <= length <= 4096:
            raise ValueError("Invalid name size")
        name_bytes = raw[offset+110:offset+110+length]
        if not name_bytes.endswith(b"\0"):
            raise ValueError("Invalid newc name")
        name = name_bytes[:-1].decode()
        offset += 110 + length
        offset += -offset % 4
        data = raw[offset:offset+size]
        offset += size
        offset += -offset % 4
        if len(data) != size:
            raise ValueError("Truncated newc")
        if name == "TRAILER!!!":
            break
        if name in seen or name.startswith("/") or ".." in name.split("/") or len(seen) >= 512:
            raise ValueError("Unsafe or oversized archive")
        seen.add(name)
        yield name, fields, data


def encode(name, fields, data):
    fields = list(fields)
    name = name.encode() + b"\0"
    fields[6], fields[11] = len(data), len(name)
    header = b"070701" + b"".join(f"{x:08x}".encode() for x in fields) + name
    return header + b"\0" * (-len(header) % 4) + data + b"\0" * (-len(data) % 4)


def derive(source, output):
    compressed = Path(source).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != BASE_SHA:
        raise ValueError("Preserved guest034 capsule mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(128 * 1024 * 1024 + 1)
    if len(raw) > 128 * 1024 * 1024:
        raise ValueError("Capsule expansion bound")
    items = {name: (fields, data) for name, fields, data in records(raw)}
    changes = {}
    def update(name, transform):
        fields, before = items[name]
        after = transform(before)
        items[name] = fields, after
        changes[name] = {"before": hashlib.sha256(before).hexdigest(), "after": hashlib.sha256(after).hexdigest()}
    update(PREFIX + "prepare_session.py", lambda raw: replace_once(raw,
        "    seed_home(Path('/home/roko'), json.loads(small(INSTALL/'seed-manifest.json')))\n",
        "    seed_home(Path('/home/roko'), json.loads(small(INSTALL/'seed-manifest.json')))\n    import foundation_state\n    foundation_state.prepare()\n"))
    def probe(raw):
        raw = replace_once(raw, "def mounts(raw):", "MOUNTS.update({'/run/roko-foundation-state': ('ext4','rw'), '/home/roko/.local/state': ('ext4','rw')})\n\ndef mounts(raw):")
        raw = replace_once(raw, "        if point in SIZES:need(", "        if point in ('/run/roko-foundation-state','/home/roko/.local/state'):need({'nosuid','nodev','noexec'}<=opts)\n        if point in SIZES:need(")
        return replace_once(raw, "roles=request(sys.stdin.buffer.read(2049));result=observe(roles,failure=failure)",
            'roles=request(sys.stdin.buffer.read(2049));result=observe(roles,failure=failure)\n        import foundation_state\n        foundation_state.user_checkpoint()')
    update(PREFIX + "evidence_probe.py", probe)
    update(PREFIX + "evidence_client.py", lambda raw: replace_once(raw,
        "        if point in SIZES or point in ('/','/run/roko-guest-cognition','/sys/fs/cgroup'):",
        "        if point in ('/run/roko-foundation-state','/home/roko/.local/state') and item[2:5]!=[1,1,1]:raise ValueError('Unsafe persistent state mount')\n        if point in SIZES or point in ('/','/run/roko-guest-cognition','/sys/fs/cgroup'):"))
    def supervisor(raw):
        raw = replace_once(raw, "            self.verify_evidence()\n",
            "            self.verify_evidence()\n            import foundation_state\n            foundation_state.root_receipt()\n")
        return replace_once(raw, "        except Exception as error:\n            failure_metadata.report_startup(error, self.evidence)",
            "        except Exception as error:\n            import foundation_state\n            foundation_state.startup_diagnostics()\n            failure_metadata.report_startup(error, self.evidence)")
    update("payload/root/usr/libexec/roko-showcase-supervisor.py", supervisor)
    helper = (HERE / "foundation_state.py").read_bytes()
    fields = [max(value[0][0] for value in items.values()) + 1, stat.S_IFREG | 0o444, 0, 0, 1, 0, len(helper), 0, 0, 0, 0, 0, 0]
    items[PREFIX + "foundation_state.py"] = fields, helper
    # Ensure no syntax errors are introduced into the modified actual guest files.
    for name in [*changes, PREFIX + "foundation_state.py"]:
        compile(items[name][1], name, "exec")
    result = b"".join(encode(name, fields, data) for name, (fields, data) in sorted(items.items()))
    result += encode("TRAILER!!!", [0]*13, b"")
    result += b"\0" * (-len(result) % 512)
    output = Path(output)
    output.mkdir(mode=0o700)
    with (output / "session.cpio.gz").open("xb") as destination:
        with gzip.GzipFile(fileobj=destination, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
            stream.write(result)
    actual = gzip.decompress((output / "session.cpio.gz").read_bytes())
    if list(records(actual)) != [(name, [*fields[:6], len(data), *fields[7:11], len(name.encode())+1, fields[12]], data) for name, (fields, data) in sorted(items.items())]:
        raise ValueError("Archive readback mismatch")
    report = {"schema": "roko-foundation-session-derive-v1", "parent_sha256": BASE_SHA,
              "sha256": hashlib.sha256((output / "session.cpio.gz").read_bytes()).hexdigest(),
              "bytes": (output / "session.cpio.gz").stat().st_size, "members": len(items),
              "changed": changes, "added_helper_sha256": hashlib.sha256(helper).hexdigest(),
              "boot_tested": False, "model_inference_tested": False}
    (output / "derivation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(derive(args.source, args.output), indent=2))
