"""Fixed workspace references. No request field can name a source or process."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKSPACE = ROOT.parent
BASE = WORKSPACE / 'omega-baseline'
RECOVERED = WORKSPACE / 'recovery-second/runtime/swipl-basic/runtime'
SWI = RECOVERED / 'swipl/lib/swipl'
PYTHON = RECOVERED / 'recovered-python312'
PETTA = BASE / 'vendor/PeTTa-omega-release'
SYSTEM = WORKSPACE / 'symbolic-ai-v4/system'
UPSTREAM = ROOT / 'upstream'
MANIFEST = ROOT / 'proof/inputs.json'
MODULES = ('core/state.metta', 'core/state_accessors.metta',
           'openpsi/config.metta', 'category/functors.metta', 'magus/decision.metta')
# PeTTa compiles each file using functions already registered at import time.
# Numeric dependencies MUST precede the upstream consumers.
IMPORTS = (HERE / 'numeric_compat.metta',) + tuple(UPSTREAM / name for name in MODULES)
