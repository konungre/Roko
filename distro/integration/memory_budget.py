"""Compatibility import for the shared read-only boot/runtime memory observer."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('roko_runtime_memory_budget',Path(__file__).resolve().parents[1]/'nix/memory_budget.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
observe=module.observe
admit=module.admit
