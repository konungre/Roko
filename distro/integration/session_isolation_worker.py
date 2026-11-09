"""Harmless heartbeat process; no desktop, model, network, requests or storage."""
import json,os,signal,sys,time
role,behavior=sys.argv[1:]
if role not in ('desktop-sentinel','ai-sentinel') or behavior not in ('steady','crash'):raise SystemExit(2)
print(json.dumps({'event':'ready','role':role,'pid':os.getpid(),'monotonic_ns':time.monotonic_ns()}),flush=True)
if behavior=='crash':raise SystemExit(17)
running=True
def stop(*args):
 global running;running=False
signal.signal(signal.SIGTERM,stop);count=0
while running:
 count+=1;print(json.dumps({'event':'heartbeat','role':role,'pid':os.getpid(),'sequence':count,'monotonic_ns':time.monotonic_ns()}),flush=True);time.sleep(.05)
