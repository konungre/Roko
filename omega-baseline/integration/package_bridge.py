"""PeTTa/Janus entry point; all exposed planning calls are read-only."""
from pathlib import Path
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adapters'))
# Trusted launcher configuration only; request/snapshot data cannot select code.
PLANNER_MODE = os.environ.get('ROKO_PACKAGE_PLANNER', 'legacy')
if PLANNER_MODE == 'legacy':
    from package_planning import plan_single, operation_count, planned_path, authorizes_actions, has_planned_package
elif PLANNER_MODE == 'successor-v2':
    from package_planning_v2 import plan_single, operation_count, planned_path, authorizes_actions, has_planned_package
else:
    raise ValueError('Unknown ROKO_PACKAGE_PLANNER; use legacy or successor-v2')
