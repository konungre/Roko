"""Fixed reviewed upstream file, no runtime-selected imports, no effects outside temp logs."""
import errno
import hashlib
import importlib.util
import logging
import os
from pathlib import Path
import socket
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from paths import HERE,UPSTREAM
from contract import MAX_REQUEST,MAX_RESPONSE,parse_request,canonical,response
from experiment import Bounds,run
from runtime_guard import runtime_maps

def file_policy(event,args):
 if event in ('os.system','subprocess.Popen','os.fork','os.forkpty','os.exec','os.posix_spawn','pty.spawn'):raise PermissionError('No subprocess operations in AIRIS slice')
 if event=='open':
  path,mode,flags=args
  writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if writing:
   if not isinstance(path,(str,bytes,os.PathLike)):raise PermissionError('No write descriptor imports')
   p=Path(os.fsdecode(path)).resolve();root=Path.cwd()
   if p.parent not in (root/'airis logs',root/'training logs') or p.suffix!='.log':raise PermissionError('Only request-local AIRIS logs writable')
 if event in ('os.chdir','os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.chmod','os.chown'):raise PermissionError('No filesystem mutation after setup')

def main():
 request=parse_request(sys.stdin.buffer.read(MAX_REQUEST+1))
 # The actual socket syscall is denied by the inherited child filter, not a mock.
 try:
  s=socket.socket();s.close()
 except OSError as e:
  if e.errno!=errno.EPERM:raise
 else:raise RuntimeError('Network negative control failed')
 runtime_maps()  # Fail before upstream import if Python used any fallback prefix/source.
 Path('airis logs').mkdir();Path('training logs').mkdir()
 sys.addaudithook(file_policy)
 upstream=UPSTREAM/'airis.py';bounds=Bounds(upstream);packet_stdout=sys.stdout
 spec=importlib.util.spec_from_file_location('roko_pinned_airis',str(upstream))
 module=importlib.util.module_from_spec(spec)
 sys.settrace(bounds.trace)
 log=None
 try:
  spec.loader.exec_module(module)
  agent=module.Airis(None,None)
  log=sys.stdout
  if log is packet_stdout:raise RuntimeError('Original constructor output route not observed')
  native=run(agent,request,bounds)
 finally:
  sys.settrace(None)
  if log is not None:log.flush();log.close()
  sys.stdout=packet_stdout
  logging.shutdown()
 packet={'version':1,'request':request,'native':native,'response':response(request,native),
  'runtime':runtime_maps(),'network_denial_observed':True,'upstream_sha256':hashlib.sha256(upstream.read_bytes()).hexdigest()}
 raw=canonical(packet)
 if len(raw)+1>MAX_RESPONSE:raise ValueError('Worker packet cap')
 sys.stderr.write('ROKO_AIRIS_OUTPUT_ROUTE_SENTINEL\n');sys.stderr.flush()
 sys.stdout.buffer.write(raw+b'\n');sys.stdout.buffer.flush()

if __name__=='__main__':main()
