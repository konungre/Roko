"""Run with python -m omega_pm. Read-only by default; apply needs --yes."""
import argparse
import json
import os
from pathlib import Path
import sys

from .backends import NixBackend, SimulationBackend, atomic_json, locked
from .core import Error, apply_plan, make_plan, parse_config, state_atoms


def main(argv=None):
    parser = argparse.ArgumentParser(description="Omega declarative package-management prototype")
    parser.add_argument("--backend", choices=["simulation", "nix"], default="simulation")
    parser.add_argument("--state-dir", type=Path,
                        default=Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "omega-pm")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report optional runtime availability without installing anything")
    observe = commands.add_parser("observe", help="Read actual state")
    observe.add_argument("--metta", action="store_true", help="Export actual state as MeTTa data atoms")
    plan = commands.add_parser("plan", help="Compare desired atoms with observed state")
    plan.add_argument("config", type=Path)
    plan.add_argument("--output", type=Path)
    apply = commands.add_parser("apply", help="Apply a reviewed plan; may partially change the profile")
    apply.add_argument("plan", type=Path)
    apply.add_argument("--yes", action="store_true", help="Confirm the plan's install and remove operations")
    check = commands.add_parser("check", help="Exit 2 if actual state differs from configuration")
    check.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    backend_type = SimulationBackend if args.backend == "simulation" else NixBackend
    backend = backend_type(args.state_dir)
    try:
        if args.command == "doctor":
            from .metta import capabilities
            output = capabilities()
        elif args.command == "observe":
            result = backend.observe()
            if args.metta:
                print(state_atoms(result), end="")
                return 0
            output = {"backend": backend.identity, **result.document()}
        elif args.command in ("plan", "check"):
            output = make_plan(backend, parse_config(args.config.read_text()))
            if args.command == "check":
                print(json.dumps({"in_sync": not output["operations"], "operations": output["operations"]}, indent=2))
                return 2 if output["operations"] else 0
            if args.output:
                atomic_json(args.output, output)
        else:
            if not args.yes:
                raise Error("Review the plan, then pass --yes to authorize applying it")
            with locked(args.state_dir / (args.backend + ".lock")):
                output = apply_plan(backend, json.loads(args.plan.read_text()))
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0
    except (Error, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"omega-pm: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
