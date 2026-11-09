"""User-initiated bounded JSON route to the separately packaged live controller."""
import json,os,selectors,signal,subprocess,time
from pathlib import Path

def _stop(proc):
 try:os.killpg(proc.pid,signal.SIGTERM)
 except ProcessLookupError:return
 try:proc.wait(timeout=8)
 except subprocess.TimeoutExpired:
  try:os.killpg(proc.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  proc.wait(timeout=3)
 # Provider descendants must not outlive a returned/cancelled UI request.
 try:os.killpg(proc.pid,signal.SIGKILL)
 except ProcessLookupError:pass

def run_live(cli,python,kind,goal,evidence,cancel_event=None,progress_callback=None,timeout=1260):
 result={'task_id':None,'proposal':None,'checked':False,'accepted':None,'error':None,'state_stale':False,'executed_actions':0}
 proc=None
 try:
  cli,python=Path(cli),Path(python)
  if not cli.is_absolute() or not python.is_absolute() or not cli.is_file() or not python.is_file():raise ValueError('Live local AI runtime is not installed at the configured path.')
  if kind not in ('quote','arithmetic','invoice'):raise ValueError('Unsupported task kind')
  if any(not isinstance(s,str) or not s.strip() or len(s)>512 or '\0' in s for s in (goal,evidence)):raise ValueError('Goal and evidence must each contain 1–512 characters.')
  if cancel_event is not None and cancel_event.is_set():raise ValueError('Request cancelled before starting.')
  payload=json.dumps({'version':1,'kind':kind,'goal':goal,'evidence':evidence},ensure_ascii=False).encode()+b'\n'
  env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
  proc=subprocess.Popen([str(python),'-I','-B',str(cli)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env=env,shell=False)
  result['state_stale']=True
  if progress_callback:progress_callback('Local model is working…')
  streams={'stdout':bytearray(),'stderr':bytearray()};sent=0;deadline=time.monotonic()+timeout
  with selectors.DefaultSelector() as sel:
   for stream,name,event in [(proc.stdin,'stdin',selectors.EVENT_WRITE),(proc.stdout,'stdout',selectors.EVENT_READ),(proc.stderr,'stderr',selectors.EVENT_READ)]:
    os.set_blocking(stream.fileno(),False);sel.register(stream,event,name)
   while sel.get_map() or proc.poll() is None:
    if cancel_event is not None and cancel_event.is_set():raise ValueError('Request cancelled. Saved progress may need reloading.')
    if time.monotonic()>deadline:raise ValueError('Local model timed out. Saved progress may need reloading.')
    for key,_ in sel.select(.05):
     if key.data=='stdin':
      count=os.write(key.fileobj.fileno(),payload[sent:]);sent+=count
      if sent==len(payload):sel.unregister(key.fileobj);key.fileobj.close()
     else:
      chunk=os.read(key.fileobj.fileno(),8192)
      if not chunk:sel.unregister(key.fileobj)
      else:
       streams[key.data].extend(chunk)
       if sum(map(len,streams.values()))>65536:raise ValueError('Local AI response exceeded the display limit.')
  try:response=json.loads(streams['stdout'])
  except ValueError:
   raise ValueError(streams['stderr'].decode(errors='replace').strip() or 'Local AI process returned no valid result.')
  if proc.returncode and (not isinstance(response,dict) or not response.get('error')):raise ValueError('Local AI process failed without a structured error.')
  if not isinstance(response,dict) or response.get('executed_actions')!=0:raise ValueError('Unexpected local AI result.')
  checked=response.get('checked')
  if isinstance(checked,dict):
   if type(checked.get('accepted')) is not bool or checked.get('authorizes_actions') is not False:raise ValueError('Unexpected independent check result.')
   if response.get('accepted') is not checked['accepted']:raise ValueError('Inconsistent check result.')
   response['verification']=checked
   response['checked']=True
  if response.get('accepted') is True and response.get('checked') is not True:raise ValueError('Unchecked result cannot be accepted.')
  result.update(response)
 except (ValueError,OSError,TypeError,subprocess.SubprocessError) as exc:result['error']=str(exc)
 finally:
  if proc is not None:
   _stop(proc)
   for stream in (proc.stdin,proc.stdout,proc.stderr):
    if not stream.closed:stream.close()
 return result
