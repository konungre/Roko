"""Fixed authored source bindings for a new local host qualification."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
UPSTREAM=ROOT/'upstream'
MODULES=('core/state.metta','core/state_accessors.metta','openpsi/config.metta',
         'category/functors.metta','magus/decision.metta')
IMPORTS=(HERE/'numeric_compat.metta',)+tuple(UPSTREAM/name for name in MODULES)
