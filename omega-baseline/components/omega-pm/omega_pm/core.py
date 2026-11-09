"""Declarative atoms, deterministic plans and a backend-independent reconciler."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Protocol


class Error(Exception):
    """An actionable input, backend, or reconciliation error."""


# The alphabet is Nix's base32 alphabet. A store path must be a single store entry.
STORE = re.compile(r"/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+\Z")
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
TOKEN = re.compile(r'\s+|;[^\n]*|[()]|"(?:[^"\\]|\\.)*"|[^\s();"]+')


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_packages(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise Error("Packages must be an object mapping names to store paths")
    for name, path in value.items():
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise Error(f"Invalid package name: {name!r}")
        if not isinstance(path, str) or not STORE.fullmatch(path):
            raise Error(f"Package {name}: expected an exact /nix/store/<hash>-<name> path")
    return dict(sorted(value.items()))


def parse_config(source: str) -> dict[str, str]:
    """Parse data atoms, never evaluate MeTTa code or execute shell expressions.

    This deliberately small language accepts (omega-config 1) and
    (package symbolic-name "absolute-store-path"), plus semicolon comments.
    """
    tokens = []
    offset = 0
    for match in TOKEN.finditer(source):
        if match.start() != offset:
            raise Error(f"Invalid syntax at character {offset}")
        offset = match.end()
        token = match.group()
        if token.isspace() or token.startswith(";"):
            continue
        tokens.append(token)
    if offset != len(source):
        raise Error(f"Invalid syntax at character {offset}")
    forms = []
    index = 0
    while index < len(tokens):
        if tokens[index] != "(":
            raise Error("Only top-level declarative atoms are supported")
        index += 1
        form = []
        while index < len(tokens) and tokens[index] != ")":
            if tokens[index] == "(":
                raise Error("Nested expressions and executable MeTTa are not supported")
            form.append(tokens[index])
            index += 1
        if index == len(tokens):
            raise Error("Unclosed atom")
        forms.append(form)
        index += 1
    if not forms or forms[0] != ["omega-config", "1"]:
        raise Error("The first atom must be (omega-config 1)")
    packages = {}
    for form in forms[1:]:
        if len(form) != 3 or form[0] != "package":
            raise Error("Expected (package name \"/nix/store/...\")")
        _, name, raw = form
        if not raw.startswith('"'):
            raise Error("Store paths must be quoted strings")
        try:
            path = json.loads(raw)
        except ValueError as exc:
            raise Error("Use JSON-compatible quoted strings") from exc
        if name in packages:
            raise Error(f"Duplicate package declaration: {name}")
        packages[name] = path
    return validate_packages(packages)


@dataclass(frozen=True)
class Snapshot:
    packages: dict[str, str]
    revision: str

    def document(self) -> dict:
        return {"packages": validate_packages(self.packages), "revision": self.revision}


class Backend(Protocol):
    identity: str

    def observe(self) -> Snapshot: ...
    def preflight(self, desired: dict[str, str]) -> None: ...
    def install(self, name: str, path: str) -> None: ...
    def remove(self, name: str) -> None: ...


def operations(actual: dict[str, str], desired: dict[str, str]) -> list[dict]:
    result = []
    for name in sorted(actual.keys() | desired.keys()):
        old, new = actual.get(name), desired.get(name)
        if old == new:
            continue
        if old is not None:
            result.append({"op": "remove", "name": name, "path": old})
        if new is not None:
            result.append({"op": "install", "name": name, "path": new})
    return result


def make_plan(backend: Backend, desired: dict[str, str]) -> dict:
    desired = validate_packages(desired)
    observed = backend.observe()
    body = {
        "schema": 1, "backend": backend.identity,
        "before": observed.document(), "desired": desired,
        "operations": operations(observed.packages, desired),
    }
    return {**body, "id": digest(body)}


def verify_plan(plan: object, backend: Backend) -> dict:
    if not isinstance(plan, dict) or set(plan) != {
        "schema", "backend", "before", "desired", "operations", "id"
    }:
        raise Error("Invalid plan fields")
    body = {key: value for key, value in plan.items() if key != "id"}
    if plan["schema"] != 1 or plan["id"] != digest(body):
        raise Error("Plan checksum or schema is invalid; generate a fresh plan")
    if plan["backend"] != backend.identity:
        raise Error("Plan targets a different backend or profile")
    before = plan["before"]
    if not isinstance(before, dict) or set(before) != {"packages", "revision"}:
        raise Error("Invalid plan snapshot")
    if not isinstance(before["revision"], str):
        raise Error("Invalid snapshot revision")
    actual = validate_packages(before["packages"])
    desired = validate_packages(plan["desired"])
    if plan["operations"] != operations(actual, desired):
        raise Error("Plan operations do not match its declared state")
    return desired


def apply_plan(backend: Backend, plan: dict) -> dict:
    """Caller holds a profile lock. External Nix clients must not modify it."""
    desired = verify_plan(plan, backend)
    if backend.observe().document() != plan["before"]:
        raise Error("State changed since planning; inspect state and generate a fresh plan")
    # Validate every desired store path before removing anything.
    backend.preflight(desired)
    completed = []
    try:
        for operation in plan["operations"]:
            if operation["op"] == "remove":
                backend.remove(operation["name"])
            else:
                backend.install(operation["name"], operation["path"])
            completed.append(operation)
        after = backend.observe()
        if after.packages != desired:
            raise Error("Post-apply observation does not match desired state")
    except Exception as exc:
        # No false atomicity claim: the caller gets partial progress, and must replan.
        raise Error(
            f"Apply stopped after {len(completed)} operation(s): {exc}. "
            "Changes may be partial. Run observe, then plan again."
        ) from exc
    return {"plan_id": plan["id"], "completed": completed, "after": after.document()}


def state_atoms(snapshot: Snapshot) -> str:
    lines = ["; Observed state, not a desired configuration", "(omega-state 1)"]
    lines += [f'(installed {name} {json.dumps(path)})'
              for name, path in sorted(snapshot.packages.items())]
    lines.append(f'(state-revision {json.dumps(snapshot.revision)})')
    return "\n".join(lines) + "\n"
