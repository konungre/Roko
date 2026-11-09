from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
WORKSPACE=ROOT.parents[1]
PYTHON=WORKSPACE/'recovery-second/runtime/swipl-basic/runtime/recovered-python312'
SYSTEM=WORKSPACE/'symbolic-ai-v4/system'
UPSTREAM=ROOT/'upstream'
MANIFEST=ROOT/'proof/inputs.json'
PYTHON_BINARY=PYTHON/'bin/python3.12'
