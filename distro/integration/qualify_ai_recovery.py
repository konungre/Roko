"""Owned-process AI failure recovery with explicit fixture choices; no services/VM."""
import argparse,hashlib,json,time
from pathlib import Path
from qualify_session_isolation import Child
from fixture_restart_choice import FixtureChoices

def qualify(output):
 output=Path(output).resolve();output.mkdir(mode=0o700);children=[];events=[];choices=FixtureChoices();spawn_count=0
 def start(role,behavior):
  nonlocal spawn_count
  child=Child(role,behavior,output,len(children));children.append(child);spawn_count+=1;child.event('ready');return child
 def heartbeat(desktop):
  row=desktop.event('heartbeat',after_ns=time.monotonic_ns());assert row['pid']==desktop.p.pid and desktop.p.poll() is None;return row
 try:
  desktop=start('desktop-sentinel','steady');heartbeat(desktop);original_desktop=desktop.p.pid
  failed=start('ai-sentinel','crash');assert failed.p.wait(timeout=1)==17;failed.stop();choices.changed()
  count=spawn_count;assert choices.apply(choices.choose('keep-stopped'),lambda:start('ai-sentinel','steady')) is None and spawn_count==count
  heartbeat(desktop);events.append({'case':'startup-failure-kept-stopped','desktop_pid':desktop.p.pid,'automatic_restarts':0})
  decision=choices.choose('restart');hung=choices.apply(decision,lambda:start('ai-sentinel','stall'))
  try:hung.event('heartbeat')
  except TimeoutError:pass
  else:raise AssertionError('stall was not detected')
  hung.stop();assert hung.p.returncode==0;choices.changed();heartbeat(desktop)
  events.append({'case':'heartbeat-deadline-cancelled','ai_returncode':0,'desktop_pid':desktop.p.pid,'ai_reaped':True})
  count=spawn_count
  try:choices.apply(decision,lambda:start('ai-sentinel','steady'))
  except ValueError:pass
  else:raise AssertionError('replayed restart accepted')
  assert spawn_count==count
  stubborn=choices.apply(choices.choose('restart'),lambda:start('ai-sentinel','ignore-term'));stubborn.event('heartbeat')
  stubborn.stop();assert stubborn.p.returncode==-9;choices.changed();heartbeat(desktop)
  events.append({'case':'termination-resistant-ai-killed','ai_returncode':-9,'desktop_pid':desktop.p.pid,'ai_reaped':True})
  healthy=choices.apply(choices.choose('restart'),lambda:start('ai-sentinel','steady'));healthy.event('heartbeat');heartbeat(desktop)
  assert desktop.p.pid==original_desktop;healthy.stop();choices.changed()
  pending=choices.choose('restart');desktop.stop();choices.changed(new_desktop=True)
  desktop=start('desktop-sentinel','steady');heartbeat(desktop);count=spawn_count
  try:choices.apply(pending,lambda:start('ai-sentinel','steady'))
  except ValueError:pass
  else:raise AssertionError('old desktop choice accepted')
  assert spawn_count==count
  events.append({'case':'desktop-epoch-invalidates-pending-choice','new_desktop_pid':desktop.p.pid,'old_desktop_reaped':True,'ai_started_from_stale_choice':False})
  fresh=choices.apply(choices.choose('restart'),lambda:start('ai-sentinel','steady'));fresh.event('heartbeat');heartbeat(desktop)
  events.append({'case':'explicit-fresh-recovery','desktop_pid':desktop.p.pid,'ai_pid':fresh.p.pid,'automatic_restarts':0})
 finally:
  for child in reversed(children):child.stop()
 report={'passed':True,'events':events,'children_started':spawn_count,'all_children_reaped':all(c.p.poll() is not None for c in children),'explicit_choices_are_fixtures':True,'authentication_tested':False,'systemd_lifecycle_tested':False,'guest_started':False,'model_or_desktop_executed':False,'host_services_activated':False,'source_hashes':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('qualify_ai_recovery.py','fixture_restart_choice.py','qualify_session_isolation.py','session_isolation_worker.py')},'scope':'owned heartbeat processes; not a production user approval channel, model endpoint or conversation replay test'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();r=qualify(a.output);print(json.dumps({'passed':r['passed'],'all_children_reaped':r['all_children_reaped'],'events':len(r['events'])}))
