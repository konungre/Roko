import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'adapters'))
from state_store import StateStore
recovered={}
def recover():
 store=StateStore(os.environ['ROKO_STATE_DIR'])
 for i in range(2):recovered[i]=store.load('live-invoice-'+str(i))
 return True
def phase(i):return recovered[int(i)][0].phase.value
def revision(i):return recovered[int(i)][1]
def unapproved():
 return all(not (s.snapshot()['verification'] or {}).get('authorizes_actions',False) for s,r in recovered.values())
def no_actions():return all(s.snapshot()['executed_actions']==0 for s,r in recovered.values())
def save():
 report={'mode':'Two prior actual live-model states written by one process and recovered by a separate PeTTa/Janus process; no fresh inference','recovered':{str(i):{'revision':r,'state':s.snapshot()} for i,(s,r) in recovered.items()},'authorizes_actions':False,'executed_actions':0,'power_loss_tested':False}
 (ROOT/'results/native-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
 return True
