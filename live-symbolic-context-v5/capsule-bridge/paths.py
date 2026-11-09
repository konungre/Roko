"""Fixed proposed guest placement, never supplied by request text."""
from pathlib import Path
ROOT = Path('/run/roko-guest-cognition/symbolic-v1')
HERE = ROOT / 'bridge'
SWI = ROOT / 'swipl'
PYTHON = ROOT / 'python'
PETTA = ROOT / 'petta'
OMEGA = ROOT / 'omega'
PRIVATE = ROOT / 'private-ecan'
SYSTEM = ROOT / 'system'
MANIFEST = ROOT / 'inputs.json'
WORK = Path('/var/lib/roko/live-requests/native-work')
ECAN_LOCK = ROOT / 'metta-attention-source.lock.json'
MODULES = (
 'attention/AttentionParam.metta',
 'attention-bank/utilities/helper-functions.metta',
 'attention-bank/attention-value/getter-and-setter.metta',
 'attention-bank/bank/attention-bank.metta',
 'attention-bank/bank/importance-index/importance-index.metta',
 'attention-bank/bank/attentional-focus/attentional-focus.metta',
 'attention-bank/utilities/recentVal.metta',
)
