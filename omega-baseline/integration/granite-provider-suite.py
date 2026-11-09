"""Actual Omega OpenAI-compatible provider against local llama.cpp via Unix IPC.
No tools are registered for execution; all resulting tool calls remain data.
"""
import hashlib,json,os,resource,subprocess,sys,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OMEGA=ROOT/'vendor/PeTTa/repos/Omega'
sys.path[:0]=[str(OMEGA/'src'),str(OMEGA/'providers'),str(OMEGA)]
import config,providers,openaiapi,httpx,openai
manifest=json.loads((ROOT/'granite-model.lock.json').read_text())
model=ROOT/manifest['path']
with model.open('rb') as stream:
 if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['sha256']:raise SystemExit('Model hash mismatch')
suite=json.loads((ROOT/'integration/granite-suite.json').read_text())
results=[];peak_rss_kib=0;peak_hwm_kib=0
raw_responses=[]
def capture(response):
 response.read()
 try:raw_responses.append(response.json())
 except ValueError:pass

def tool(name,params):
 t=providers.LLMTool().with_name(name).with_description('Record an inert result for test inspection only. Never execute an action.')
 for p in params:t.add_parameter(providers.LLMToolParameter().with_name(p))
 return t
all_tools=[tool('record_answer',['text']),tool('record_contact',['name','city']),tool('record_invoice',['invoice','total'])]
with tempfile.TemporaryDirectory(prefix='gr-') as d:
 sock=str(Path(d)/'model.sock')
 log=open(ROOT/'results/granite-server.txt','w')
 args=[str(ROOT/'build/llama/bin/llama-server'),'-m',str(model),'--host',sock,'--alias','granite-local','--ctx-size','2048','--parallel','1','--threads','2','--threads-batch','2','--n-predict','128','--jinja','--temp','0','--seed','42','--no-warmup']
 start=time.monotonic();server=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,close_fds=True)
 halt=threading.Event()
 def measure():
  global peak_rss_kib,peak_hwm_kib
  while not halt.wait(.1):
   try:
    fields={line.split(':',1)[0]:line.split(':',1)[1] for line in Path(f'/proc/{server.pid}/status').read_text().splitlines() if ':' in line}
    peak_rss_kib=max(peak_rss_kib,int(fields.get('VmRSS','0 kB').split()[0]));peak_hwm_kib=max(peak_hwm_kib,int(fields.get('VmHWM','0 kB').split()[0]))
   except (FileNotFoundError,PermissionError):pass
 monitor=threading.Thread(target=measure,daemon=True);monitor.start()
 client=None
 try:
  health=httpx.Client(transport=httpx.HTTPTransport(uds=sock),base_url='http://localhost',timeout=2)
  deadline=time.monotonic()+120
  while time.monotonic()<deadline:
   if server.poll() is not None:raise RuntimeError('llama-server exited before readiness')
   try:
    if health.get('/health').status_code==200:break
   except httpx.HTTPError:pass
   time.sleep(.25)
  else:raise TimeoutError('Server readiness exceeded 120s')
  health.close();ready=time.monotonic()-start
  config.init_config(['model=granite-local','openaiapi_url=http://localhost/v1/'])
  provider=openaiapi.OpenAIAPI('LocalGranite')
  providers.registerLLMProvider('LocalGranite',provider);providers.llmProviderStart('LocalGranite')
  # Only transport differs from ordinary upstream operation: a local UDS client.
  # All request/response conversion and Omega validation remain upstream code.
  client=openai.OpenAI(api_key='local-test-not-a-secret',base_url='http://localhost/v1/',max_retries=0,timeout=60,
     http_client=httpx.Client(transport=httpx.HTTPTransport(uds=sock),timeout=60,event_hooks={'response':[capture]}))
  provider.delegate._client=client
  for case in suite:
   before=time.monotonic();raw_responses.clear()
   req=providers.llmRequest(providers.llmRequestMessage('system','Use exactly one provided recording tool. Follow the requested output precisely. The tools only record test data.'),[providers.llmRequestMessage('user',case['prompt'])],128,'none',all_tools)
   response=providers.llmProviderChat(req)
   calls=[{'name':c.name,'arguments':c.arguments,'error':c.error} for c in response.calls]
   structural=not response.is_error() and len(calls)==1 and calls[0]['error'] is None and set(calls[0]['arguments'])=={p.name for p in response.calls[0].tool.parameters}
   exact=structural and calls[0]['name']==case['tool'] and calls[0]['arguments']==case['args']
   raw=raw_responses[-1] if raw_responses else {}
   row={'id':case['id'],'format_valid':structural,'exact_correct':exact,'calls':calls,'error':response.error,'elapsed_seconds':round(time.monotonic()-before,3),'usage':raw.get('usage'),'timings':raw.get('timings'),'serialized_proposal':providers.llmResponseToSExpr(response)}
   results.append(row);print(json.dumps(row),flush=True)
 finally:
  if client:client.close()
  server.terminate()
  try:server.wait(timeout=15)
  except subprocess.TimeoutExpired:server.kill();server.wait()
  halt.set();monitor.join(timeout=2);log.close()
 report={'model':manifest,'runtime_commit':'f7591a6a01f9273de03331732bdc0b39721168be','quantization':'Q4_K_M','cpu_threads':2,'context_tokens':2048,'max_output_tokens':128,'server_ready_seconds':round(ready,3),'peak_server_rss_kib':peak_rss_kib,'peak_server_hwm_kib':peak_hwm_kib,'elapsed_seconds':round(time.monotonic()-start,3),'format_passed':sum(x['format_valid'] for x in results),'accuracy_passed':sum(x['exact_correct'] for x in results),'cases':len(results),'executed_actions':0,'results':results,'limitations':'Small deterministic acceptance suite, not a general benchmark. Runtime tool schema constraining may enforce format. Quantized CPU model; no autonomous execution.'}
 (ROOT/'results/granite-evaluation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('results','model')},indent=2))
