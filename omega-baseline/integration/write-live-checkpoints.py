"""Persist previously recorded real live-controller states, without new inference."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'adapters'))
from state_store import StateStore,restore
report=json.loads((ROOT/'results/live-controller.json').read_text())
store=StateStore(sys.argv[1])
for row in report['results']:
 state=restore(row['state'])
 assert store.save(state,expected_revision=0)==1
print('Saved two prior live-controller states with fresh invariant checks')
