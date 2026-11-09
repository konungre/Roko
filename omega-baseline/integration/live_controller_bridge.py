"""Finite live Omega -> Granite -> controller evidence gate; never dispatch tools."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'vendor/PeTTa/repos/Omega'
sys.path[:0]=[str(O/'src'),str(O/'providers'),str(O),str(ROOT/'adapters')]
import providers
from granite_pipe import GranitePipeProvider,ALLOWED
from working_state import WorkingState,invoice_evidence
provider=None
rows=[]
def start():
 global provider,rows
 rows=[]
 provider=GranitePipeProvider(ROOT,constrained=True)
 providers.registerLLMProvider('GranitePipe',provider)
 providers.llmProviderStart('GranitePipe')
 return True
def run_case(index):
 index=int(index)
 fixtures=[
 ('Invoice A17; total 42.50.','Extract this invoice: Invoice A17; total 42.50. Use record_invoice. Keep the decimal precision and omit currency symbols.'),
 ('Invoice 0007; total 0.50.','Record invoice identifier 0007 and total 0.50. Preserve leading zeros and decimal places; do not include labels.')
 ]
 source,prompt=fixtures[index]
 task_id='live-invoice-'+str(index)
 state=WorkingState(task_id,'Extract fields only from the supplied invoice evidence')
 initially_empty=state.snapshot()['evidence']=={}
 state.add_evidence('source','fixture:live-controller/'+str(index),source)
 tools=[]
 for name,params in ALLOWED.items():
  tool=providers.LLMTool().with_name(name).with_description('Record inert test data for inspection. No action is executed.')
  for p in params:tool.add_parameter(providers.LLMToolParameter().with_name(p))
  tools.append(tool)
 request=providers.llmRequest(providers.llmRequestMessage('system','Use exactly one provided recording tool. Follow the requested output precisely.'),[providers.llmRequestMessage('user',prompt)],128,'none',tools)
 began=time.monotonic()
 response=providers.llmProviderChat(request)
 calls=[{'name':c.name,'arguments':c.arguments,'error':c.error} for c in response.calls]
 format_valid=not response.is_error() and len(calls)==1 and calls[0]['error'] is None
 rejection=None;accepted=False
 if format_valid:
  try:
   state.propose(task_id,calls[0]['name'],calls[0]['arguments'],['source'])
   accepted=state.verify_invoice()['accepted']
   if accepted:state.close()
  except ValueError as e:rejection=str(e)
 else:rejection=response.error or 'invalid tool contract'
 # Compute consistency independently of controller transitions from exact source grammar.
 expected=invoice_evidence(source)
 exact=bool(format_valid and calls[0]['name']=='record_invoice' and calls[0]['arguments']==expected)
 snapshot=state.snapshot()
 consistent=(accepted==exact and snapshot['phase']==('closed' if exact else 'open'))
 row={'case':index,'mode':'fresh native model inference','format_valid':format_valid,'exact_correct':exact,'gate_accepted':accepted,'gate_consistent':consistent,'new_task_initially_empty':initially_empty,'proposal':calls,'state':snapshot,'rejection':rejection,'raw_model_output':provider.last.get('raw_output'),'elapsed_seconds':round(time.monotonic()-began,3),'native_peak_rss_kib':provider.last.get('peak_rss_kib'),'executed_actions':0}
 rows.append(row)
 (ROOT/f'results/live-controller-{index}-native.txt').write_text(provider.last.get('stderr',''))
 return format_valid
def consistent(index):return rows[int(index)]['gate_consistent']
def isolated(index):return rows[int(index)]['new_task_initially_empty']
def unauthorized():
 return all(not (r['state'].get('verification') or {}).get('authorizes_actions',False) and r['executed_actions']==0 for r in rows)
def save():
 report={'cases':len(rows),'format_passed':sum(r['format_valid'] for r in rows),'exact_correct':sum(r['exact_correct'] for r in rows),'gate_consistent':all(r['gate_consistent'] for r in rows),'executed_actions':0,'results':rows,'limitations':'Two authored invoice fixtures, strict source grammar, no general entailment or durable state. Fresh inference through real Omega and PeTTa/Janus; no proposal evaluation or dispatch.'}
 (ROOT/'results/live-controller.json').write_text(json.dumps(report,indent=2)+'\n')
 provider.stop()
 return True
