"""Local simulation and Nix >= 2.24 named-profile adapters."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .core import Error, Snapshot, digest, validate_packages


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".omega-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


class SimulationBackend:
    """Persistent test double. Never installs packages or pretends to run Nix."""
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.path = self.root / "simulation.json"
        self.identity = f"simulation:{self.path}"

    def observe(self) -> Snapshot:
        if not self.path.exists():
            return Snapshot({}, "0")
        data = json.loads(self.path.read_text())
        if set(data) != {"packages", "generation"} or type(data["generation"]) is not int:
            raise Error("Invalid simulation state")
        return Snapshot(validate_packages(data["packages"]), str(data["generation"]))

    def preflight(self, desired: dict[str, str]) -> None:
        validate_packages(desired)

    def _save(self, packages: dict[str, str], revision: str) -> None:
        atomic_json(self.path, {"packages": packages, "generation": int(revision) + 1})

    def install(self, name: str, path: str) -> None:
        snapshot = self.observe()
        snapshot.packages[name] = path
        self._save(snapshot.packages, snapshot.revision)

    def remove(self, name: str) -> None:
        snapshot = self.observe()
        del snapshot.packages[name]
        self._save(snapshot.packages, snapshot.revision)


class NixBackend:
    """A dedicated user-owned profile; no sudo, shell, daemon changes or fetching.

    Adapter targets the Nix 2.24+ profile list JSON and --name interface.
    The profile belongs exclusively to Omega; foreign elements are rejected.
    """
    def __init__(self, root: Path, runner=subprocess.run):
        self.root = root.absolute()
        self.profile = self.root / "profile"
        self.identity = f"nix:{self.profile}"
        self.runner = runner

    def _run(self, *arguments: str) -> str:
        if self.runner is subprocess.run and shutil.which("nix") is None:
            raise Error("Nix is not installed. Install Nix >= 2.24 or use --backend simulation")
        command = ["nix", "--extra-experimental-features", "nix-command flakes", "--offline", *arguments]
        try:
            result = self.runner(command, text=True, capture_output=True, check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Error(f"Could not run Nix: {exc}") from exc
        if result.returncode:
            raise Error(f"Nix failed ({result.returncode}): {result.stderr.strip()}")
        return result.stdout

    def observe(self) -> Snapshot:
        # lexists detects broken profile links; do not silently treat them as empty.
        if not os.path.lexists(self.profile):
            return Snapshot({}, "absent")
        data = json.loads(self._run("profile", "list", "--profile", str(self.profile), "--json"))
        if not isinstance(data, dict) or not isinstance(data.get("elements"), dict):
            raise Error("Unsupported Nix profile JSON; expected named elements (Nix >= 2.24)")
        packages = {}
        for key, element in data["elements"].items():
            paths = element.get("storePaths") if isinstance(element, dict) else None
            if not key.startswith("omega-") or not isinstance(paths, list) or len(paths) != 1:
                raise Error("Profile contains foreign or unsupported elements; refusing to manage it")
            if element.get("active", True) is not True:
                raise Error("Inactive Nix profile elements are unsupported")
            packages[key[len("omega-"):]] = paths[0]
        # Generation target catches drift even if the package set later returns to equal.
        revision = digest({"manifest": data, "target": str(self.profile.resolve())})
        return Snapshot(validate_packages(packages), revision)

    def preflight(self, desired: dict[str, str]) -> None:
        if os.geteuid() == 0:
            raise Error("Run the Nix backend as an ordinary user, not root")
        validate_packages(desired)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_uid != os.geteuid():
            raise Error("State directory is not owned by the current user")
        for path in sorted(set(desired.values())):
            # Reject unavailable direct paths before touching the profile. profile install
            # will also fail offline if any referenced dependency is unavailable.
            self._run("path-info", "--recursive", path)

    def install(self, name: str, path: str) -> None:
        self._run("profile", "install", "--profile", str(self.profile), "--name", "omega-" + name, path)

    def remove(self, name: str) -> None:
        self._run("profile", "remove", "--profile", str(self.profile), "omega-" + name)
