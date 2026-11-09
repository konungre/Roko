"""Independent bounded host checks for the new COSMIC/state qualification receipt."""
import json


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("Duplicate evidence field")
        result[key] = value
    return result


def validate(log, phase):
    if phase not in ("write", "read") or len(log.encode()) > 2 * 1024**2:
        raise ValueError("Invalid phase or oversized serial log")
    lines = log.splitlines()
    required = ["ROKO_FOUNDATION_STATE_MOUNTED " + phase,
                "ROKO_FOUNDATION_STATE_VERIFIED " + phase + " uid=1000 revision=1",
                "ROKO_DESKTOP_READY uid=1000 inference=not-started"]
    positions = [lines.index(line) if lines.count(line) == 1 else -1 for line in required]
    if -1 in positions or positions != sorted(positions): raise ValueError("Missing/duplicate/reordered session markers")
    if any(marker in log for marker in ("ROKO_START_FAILED", "ROKO_UNPRIVILEGED_PREPARE_FAILED", "ROKO_LIVE_BOOT_FAILED", "ROKO_RECOVERY", "ROKO_INERT_RECOVERY", "ROKO_ROLE_EXIT_META_V1", "Kernel panic")):
        raise ValueError("Guest reported failure")
    raw = [line.removeprefix("ROKO_EVIDENCE_V1 ") for line in lines if line.startswith("ROKO_EVIDENCE_V1 ")]
    if len(raw) != 1 or len(raw[0]) > 65536: raise ValueError("Expected one bounded identity record")
    row = json.loads(raw[0], object_pairs_hook=unique)
    if type(row) is not dict or set(row)!={"version","ok","processes","roles","mounts","metadata","devices","fds","peer","usability","udev","server_peer"}: raise ValueError("Unexpected evidence schema")
    if any(type(row[k]) is not int for k in ("version","ok","usability","udev")) or row["usability"]!=0 or row["udev"]!=0: raise ValueError("Unexpected evidence qualifiers")
    if row.get("version") != 1 or row.get("ok") != 1 or row.get("peer") != [1,0,0]:
        raise ValueError("Guest identity proof incomplete")
    roles = row["roles"]
    if (not isinstance(roles,list) or len(roles)!=6 or any(type(r) is not list or len(r)!=2 or r[0]!=i or type(r[1]) is not int or r[1]<=1 for i,r in enumerate(roles))
            or len({r[1] for r in roles})!=6): raise ValueError("Invalid owned role set")
    root = {1, roles[5][1]}
    seen = set()
    for process in row["processes"]:
        if type(process) is not list or len(process)!=18 or any(type(n) is not int or n<0 for n in process[:16]) or type(process[17]) is not int:
            raise ValueError("Malformed process identity")
        pid = process[0]
        if pid<=0 or pid in seen: raise ValueError("Duplicate process")
        seen.add(pid)
        if pid in root:
            if process[2:10]!=[0]*8 or process[17]!=0: raise ValueError("Root exception mismatch")
        elif process[2:10]!=[1000]*8 or process[10:15]!=[0]*5 or process[15]!=1 or process[16]!=[] or process[17] not in (1,2):
            raise ValueError("Non-root identity/capability/cgroup mismatch")
    if not root.issubset(seen) or not {r[1] for r in roles}.issubset(seen): raise ValueError("Missing role observations")
    peer = row.get("server_peer")
    if type(peer) is not list or len(peer)!=3 or peer[1:]!=[1000,1000] or peer[0] not in seen-root:
        raise ValueError("Two-sided IPC credential mismatch")
    mounts = row["mounts"]
    if type(mounts) is not list or len(mounts)!=18 or any(type(m) is not list or len(m)!=6 or m[0]!=i or any(type(n) is not int or n<0 for n in m) for i,m in enumerate(mounts)):
        raise ValueError("Unexpected mount inventory")
    if mounts[0][1:4] != [1,1,1] or mounts[8][1:4] != [1,1,1]: raise ValueError("Mutable code/root")
    if mounts[16] != [16,0,1,1,1,0] or mounts[17] != [17,0,1,1,1,0]: raise ValueError("Unsafe persistent state mount")
    if type(row["metadata"]) is not list or len(row["metadata"])!=5: raise ValueError("Incomplete metadata")
    if row["metadata"][:3] != [[i,1000,1000,0o700] for i in range(3)]: raise ValueError("Nonprivate user directory")
    return {"startup_identity_passed":True, "persistent_checkpoint_passed":True,
            "observed_nonroot_processes":len(seen-root), "model_inference_tested":False,
            "visible_desktop_verified":False}
