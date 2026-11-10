"""Guest-only controller; refuses ordinary host execution before any systemctl call."""
import json,os,pathlib,socket,subprocess,traceback,time
try:
 guest_marker=pathlib.Path('/etc/roko-service-manager-fixture').read_text().strip()
 guest_pid1=pathlib.Path('/proc/1/comm').read_text().strip()
except OSError:
 raise SystemExit(77)
if os.geteuid()!=0 or guest_marker!='roko-disposable-service-manager-v1' or guest_pid1!='systemd':raise SystemExit(77)
P=pathlib.Path('/etc/roko/first-boot.json');O=pathlib.Path('/run/roko-startup/status.json')
def ctl(*args,check=True):
 r=subprocess.run(['/usr/bin/systemctl',*args],capture_output=True,text=True,timeout=20)
 if check and r.returncode:raise RuntimeError(str(args)+': '+r.stderr)
 return r
policy={'schema':'roko-first-boot-policy-v1','offlineRequested':True,'networkIsolationProven':False,'automaticUpgrade':False,'automaticGenerationDeletion':False,'modelReady':False,'durableHistoryReady':False,'credentialProvisioningRequired':True}
try:
 print('ROKO_MANAGER_FIXTURE_BEGIN',flush=True)
 assert not pathlib.Path('/opt/roko/model').exists()
 s=socket.socket();s.settimeout(.2)
 try:s.connect(('192.0.2.1',9))
 except OSError:network_unavailable=True
 else:network_unavailable=False
 s.close();assert network_unavailable
 P.write_text(json.dumps(policy));ctl('start','roko-startup-report.service')
 first=json.loads(O.read_text());assert first['status']=='unqualified' and not first['system_ready'] and 'model-not-qualified' in first['issues']
 assert ctl('is-active','roko-startup-report.service').stdout.strip()=='active'
 print('ROKO_MANAGER_PHASE '+json.dumps({'phase':'missing-model-network-unavailable','report':first,'network_unavailable':True}),flush=True)
 P.write_text('{invalid');ctl('restart','roko-startup-report.service',check=False)
 assert ctl('is-failed','roko-startup-report.service').stdout.strip()=='failed'
 failed=json.loads(O.read_text());assert failed['status']=='failed'
 for attempt in range(30):
  invocation=ctl('show','roko-startup-report-failure.service','--property=ExecMainStartTimestampMonotonic','--value').stdout.strip()
  if invocation and int(invocation)>0:break
  time.sleep(.1)
 else:raise AssertionError('OnFailure did not execute')
 assert ctl('show','roko-startup-report-failure.service','--property=Result','--value').stdout.strip()=='success'
 print('ROKO_MANAGER_PHASE '+json.dumps({'phase':'invalid-policy','report':failed}),flush=True)
 P.write_text(json.dumps(policy));ctl('reset-failed','roko-startup-report.service');ctl('start','roko-startup-report.service')
 recovered=json.loads(O.read_text());assert recovered['status']=='unqualified' and recovered['boot_id']==first['boot_id'] and not recovered['system_ready']
 print('ROKO_MANAGER_PHASE '+json.dumps({'phase':'recovery','report':recovered}),flush=True)
 print('ROKO_MANAGER_FIXTURE_PASS',flush=True)
except BaseException:
 traceback.print_exc();print('ROKO_MANAGER_FIXTURE_FAIL',flush=True)
finally:
 ctl('--force','--force','poweroff',check=False)
