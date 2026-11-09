"""Source-defined host paths. No request chooses a runtime, file or import."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
WORKSPACE=ROOT.parent
SWI=WORKSPACE/'recovery-second/runtime/swipl-basic/runtime/swipl/lib/swipl'
PYTHON=WORKSPACE/'recovery-second/runtime/swipl-basic/runtime/recovered-python312'
PETTA=WORKSPACE/'omega-baseline/vendor/PeTTa-omega-release'
SYSTEM=WORKSPACE/'symbolic-ai-v4/system'
UPSTREAM=ROOT/'upstream'
MANIFEST=ROOT/'proof/inputs.json'
MODULES=('truthfunctions.metta','nal1.metta')
