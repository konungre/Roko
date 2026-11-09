"""Fixed wrapper stage: install child network denial, then select matched ABI."""
import json
import os
from pathlib import Path
import runpy
import sys

# The trusted parent supplies this environment and fixed no-network script path.
# This module is never selected by conversation request data.
matched = json.loads(os.environ.pop('ROKO_MATCHED_ENV'))
script, *command = sys.argv[1:]
original_execvp = os.execvp

def exec_matched(file, argv):
    os.execve(file, argv, matched)

os.execvp = exec_matched
sys.argv = [script, *command]
runpy.run_path(script, run_name='__main__')
