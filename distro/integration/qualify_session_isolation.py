"""Bounded owned-process lifecycle fixture + native static unit verification."""
import argparse,hashlib,json,os,resource,select,shutil,signal,subprocess,sys,time
from pathlib import Path
from session_isolation_policy import verify,DESKTOP,AI
HERE=Path(__file__).resolve().parent

def limits():
 resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(2,2));resource.setrlimit(resource.RLIMIT_NOFILE,(32,32));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
class Child:
 def __init__(self,role,behavior,output,index):
  self.raw=bytearray();self.pending=b'';self.events=[];self.output=output;self.index=index;self.closed=False
  self.p=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'session_isolation_worker.py'),role,behavior],stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,start_new_session=True,preexec_fn=limits,env={'PATH':'/usr/bin:/bin','LANG':'C'})
  os.set_blocking(self.p.stdout.fileno(),False)
 def read(self):
  try:block=os.read(self.p.stdout.fileno(),4096)
  except BlockingIOError:return
  self.raw.extend(block)
  if len(self.raw)>16384:raise ValueError('fixture output cap')
  self.pending+=block
  while b'\n' in self.pending:
   line,self.pending=self.pending.split(b'\n',1);self.events.append(json.loads(line))
 def event(self,name,after_ns=0):
  end=time.monotonic()+2
  while time.monotonic()<end:
   self.read()
   while self.events:
    event=self.events.pop(0)
    if event['event']==name and event['monotonic_ns']>=after_ns:return event
   if self.p.poll() is not None:raise ValueError('sentinel exited before event')
   select.select([self.p.stdout],[],[],.05)
  raise TimeoutError('sentinel event deadline')
 def stop(self):
  if self.closed:return
  try:
   if self.p.poll() is None:
    if os.getpgid(self.p.pid)!=self.p.pid:raise ValueError('owned session required')
    os.killpg(self.p.pid,signal.SIGTERM)
   try:self.p.wait(timeout=1)
   except subprocess.TimeoutExpired:os.killpg(self.p.pid,signal.SIGKILL);self.p.wait(timeout=1)
   self.read();(self.output/(str(self.index)+'.stdout')).write_bytes(self.raw);(self.output/(str(self.index)+'.stderr')).write_bytes(self.p.stderr.read(4096))
  finally:self.p.stdout.close();self.p.stderr.close();self.closed=True

def qualify(output):
 output=Path(output).resolve();output.mkdir(mode=0o700);units=output/'units';units.mkdir();source=HERE.parent/'session/fixtures/isolation';texts={}
 for name in (DESKTOP,AI):shutil.copy2(source/name,units/name);texts[name]=(units/name).read_text()
 policy=verify(texts)
 for name in ('run','home'):(output/name).mkdir(mode=0o700)
 check=subprocess.run(['/usr/bin/systemd-analyze','--user','--generators=no','--man=no','--recursive-errors=yes','verify',str(units/DESKTOP),str(units/AI)],env={'PATH':'/usr/bin:/bin','HOME':str(output/'home'),'XDG_RUNTIME_DIR':str(output/'run'),'SYSTEMD_UNIT_PATH':str(units)},capture_output=True,text=True,timeout=5,preexec_fn=limits)
 (output/'verify.stdout').write_text(check.stdout);(output/'verify.stderr').write_text(check.stderr)
 if check.returncode:raise ValueError('native static unit verification failed')
 children=[];rows=[]
 def start(role,behavior):
  child=Child(role,behavior,output,len(children));children.append(child);event=child.event('ready');assert event['pid']==child.p.pid;return child
 try:
  desktop=start('desktop-sentinel','steady');desktop.event('heartbeat');desktop_pid=desktop.p.pid
  for attempt in range(2):
   failed=start('ai-sentinel','crash');assert failed.p.wait(timeout=1)==17;failed.stop()
   beat=desktop.event('heartbeat',after_ns=time.monotonic_ns());assert desktop.p.poll() is None and beat['pid']==desktop_pid
   rows.append({'case':'explicit-ai-crash-'+str(attempt+1),'ai_returncode':17,'desktop_pid':desktop_pid,'desktop_alive':True,'automatic_restarts':0})
  ai=start('ai-sentinel','steady');ai.event('heartbeat');old_ai=ai.p.pid
  rows.append({'case':'explicit-ai-recovery','ai_pid':old_ai,'desktop_pid':desktop_pid,'desktop_alive':desktop.p.poll() is None})
  # Fixture owner cancellation policy, not live systemd propagation execution.
  ai.stop();desktop.stop();assert ai.p.poll() is not None and desktop.p.poll() is not None
  desktop=start('desktop-sentinel','steady');desktop.event('heartbeat')
  assert desktop.p.pid!=desktop_pid and ai.closed and ai.p.poll() is not None
  rows.append({'case':'desktop-restart','new_desktop_pid':desktop.p.pid,'old_ai_reaped':True,'ai_automatically_restarted':False})
  fresh=start('ai-sentinel','steady');fresh.event('heartbeat');assert fresh.p.pid!=old_ai
  rows.append({'case':'explicit-new-ai-session','ai_pid':fresh.p.pid,'desktop_pid':desktop.p.pid,'request_replay_attempted':False})
 finally:
  for child in reversed(children):child.stop()
 report={'passed':True,'policy':policy,'native_static_verify_passed':True,'systemd_units_executed':False,'cases':rows,'all_children_reaped':all(c.p.poll() is not None for c in children),'children_started':len(children),'limits':{'address_space_mib_per_child':64,'cpu_seconds_per_child':2,'output_bytes_per_sentinel':16384,'per_event_wall_seconds':2},'unit_hashes':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in texts.items()},'source_hashes':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('qualify_session_isolation.py','session_isolation_policy.py','session_isolation_worker.py')},'systemd_analyze_sha256':hashlib.sha256(Path('/usr/bin/systemd-analyze').read_bytes()).hexdigest(),'guest_started':False,'host_services_activated':False,'desktop_or_model_executed':False,'scope':'actual owned heartbeat processes plus static systemd unit checks; not COSMIC, inference, live systemd lifecycle or no-request-replay proof'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();r=qualify(a.output);print(json.dumps({'passed':r['passed'],'all_children_reaped':r['all_children_reaped'],'cases':len(r['cases'])}))
