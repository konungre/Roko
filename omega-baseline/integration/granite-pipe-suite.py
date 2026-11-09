import json,sys,time,statistics,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'vendor/PeTTa/repos/Omega'
sys.path[:0]=[str(O/'src'),str(O/'providers'),str(O),str(ROOT/'adapters')]
import providers
from granite_pipe import GranitePipeProvider,ALLOWED
mode=os.environ.get('ROKO_GRAMMAR','0')=='1'
prefix=os.environ.get('ROKO_REPORT_PREFIX','granite')
suite=json.loads((ROOT/os.environ.get('ROKO_SUITE','integration/granite-suite.json')).read_text())
provider=GranitePipeProvider(ROOT,constrained=mode);providers.registerLLMProvider('GranitePipe',provider)
start=time.monotonic();providers.llmProviderStart('GranitePipe');startup=time.monotonic()-start
all_tools=[]
for name,params in ALLOWED.items():
 t=providers.LLMTool().with_name(name).with_description('Record inert test data for inspection. No action is executed.')
 for p in params:t.add_parameter(providers.LLMToolParameter().with_name(p))
 all_tools.append(t)
rows=[]
try:
 for case in suite:
  req=providers.llmRequest(providers.llmRequestMessage('system','Use exactly one provided recording tool. Follow the requested output precisely.'),[providers.llmRequestMessage('user',case['prompt'])],128,'none',all_tools)
  response=providers.llmProviderChat(req)
  calls=[{'name':c.name,'arguments':c.arguments,'error':c.error} for c in response.calls]
  format_ok=not response.is_error() and len(calls)==1 and calls[0]['error'] is None
  exact=format_ok and calls[0]['name']==case['tool'] and calls[0]['arguments']==case['args']
  row={'id':case['id'],'format_valid':format_ok,'exact_correct':exact,'calls':calls,'error':response.error,**{k:v for k,v in provider.last.items() if k!='stderr'},'serialized_proposal':providers.llmResponseToSExpr(response)}
  (ROOT/f'results/{prefix}-{case["id"]}-native.txt').write_text(provider.last.get('stderr',''))
  rows.append(row);print(json.dumps(row),flush=True)
finally:provider.stop()
report={'model':provider.lock,'runtime_commit':'f7591a6a01f9273de03331732bdc0b39721168be','quantization':'Q4_K_M','cpu_threads':2,'context_tokens':2048,'max_output_tokens':128,'startup_validation_seconds':round(startup,3),'peak_native_rss_kib':max((r.get('peak_rss_kib',0) for r in rows),default=0),'elapsed_seconds':round(time.monotonic()-start,3),'format_passed':sum(r['format_valid'] for r in rows),'accuracy_passed':sum(r['exact_correct'] for r in rows),'cases':len(rows),'executed_actions':0,'results':rows,'arguments_mode':'one explicit JSON-text decode or direct object', 'limitations':'Small exact-match acceptance suite, not a broad benchmark. No constrained decoding, plain-text repair or schema repair. Model reloads each case; latency includes loading. Native model-generated tool proposals are validated but never executed.'}
report['constrained_decoding']=mode
report['limitations']='Small authored exact-match suite, not broad model benchmark. GBNF enforces syntax only when enabled; validator still checks each proposal. No actions executed. Model reloads each request.'
report['median_request_seconds']=statistics.median(r['elapsed_seconds'] for r in rows)
report['median_decode_tokens_per_second']=statistics.median(r['decode_tokens_per_second'] for r in rows if r.get('decode_tokens_per_second'))
(ROOT/f'results/{prefix}-evaluation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('model','results')},indent=2))
