"""Replay a recorded real Granite proposal through deterministic working state."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'adapters'))
from working_state import WorkingState,invoice_evidence
state=None
report={}
def initialize():
 global state,report
 state=WorkingState('invoice-test','Extract invoice fields from supplied evidence')
 state.add_evidence('invoice-source','fixture:granite-suite/invoice_extraction','Invoice A17; total 42.50.')
 report={'mode':'Replay of recorded real Granite output, not new model inference','executed_actions':0}
 return True
def replay_model():
 data=json.loads((ROOT/'results/granite-constrained-evaluation.json').read_text())
 row=next(r for r in data['results'] if r['id']=='invoice_extraction')
 call=row['calls'][0]
 state.propose('invoice-test',call['name'],call['arguments'],['invoice-source'])
 result=state.verify_invoice()
 report['recorded_model_proposal']=call
 report['recorded_model_check']=result
 report['after_model_check']=state.snapshot()
 return result['accepted']
def deterministic_proposal():
 # Explicit separate source extraction, not a claimed corrected model answer.
 args=invoice_evidence('Invoice A17; total 42.50.')
 state.propose('invoice-test','record_invoice',args,['invoice-source'])
 return state.verify_invoice()['accepted']
def phase():return state.phase.value
def permission():return state.snapshot()['verification']['authorizes_actions']
def close():state.close();return True
def isolated():return WorkingState('second-task','Independent task').snapshot()['evidence']=={}
def save():
 report['final_state']=state.snapshot()
 report['new_task_isolated']=isolated()
 (ROOT/'results/controller-state-native.json').write_text(json.dumps(report,indent=2)+'\n')
 return True
