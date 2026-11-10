"""Opt-in PeTTa/Janus successor; read-only scalar JSON snapshot planning."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters'))
from package_planning_v2 import plan_single,operation_count,planned_path,authorizes_actions,has_planned_package
