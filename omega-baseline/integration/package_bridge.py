"""PeTTa/Janus entry point; all exposed planning calls are read-only."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adapters'))
from package_planning import plan_single, operation_count, planned_path, authorizes_actions, has_planned_package
