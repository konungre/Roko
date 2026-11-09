"""Controlled process-crash/concurrency fixture; never used by production store."""
import os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'adapters'))
from state_store import StateStore,RevisionConflict
directory,mode=sys.argv[1:3]
store=StateStore(directory);state,revision=store.load('invoice');state.verify_invoice()
if mode in ('temp_synced','replaced'):
 def crash(stage):
  if stage==mode:os._exit(71)
 store._stage=crash
elif mode=='race':
 ready=Path(directory)/('ready-'+str(os.getpid()));ready.write_text('loaded')
 limit=time.monotonic()+10
 while not (Path(directory)/'go').exists():
  if time.monotonic()>limit:raise SystemExit(4)
  time.sleep(.01)
try:store.save(state,expected_revision=revision)
except RevisionConflict:raise SystemExit(3)
