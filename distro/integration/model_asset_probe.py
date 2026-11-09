"""Read-only GGUF asset observation, never an inference/readiness claim."""
import argparse,json,os,stat,struct
from pathlib import Path
from startup_report import write_report
def inspect(path,expected_bytes):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_size!=expected_bytes or before.st_size<24:raise ValueError('unexpected model asset')
  header=os.read(fd,24);after=os.fstat(fd)
  magic,version,tensors,metadata=struct.unpack('<4sIQQ',header)
  if magic!=b'GGUF' or version not in (2,3) or not tensors or not metadata:raise ValueError('invalid GGUF header')
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('asset changed')
 finally:os.close(fd)
 return {'schema':'roko-model-asset-observation-v1','status':'asset-observed-not-inference-qualified','bytes':before.st_size,'gguf_version':version,'tensor_count':tensors,'metadata_count':metadata,'model_sha256_verified_in_guest':False,'inference_qualified':False,'system_ready':False,'execution_authorized':False,'writer_uid':os.getuid(),'scope':'regular-file size and GGUF header only; controller separately binds read-only disk identity'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--expected-bytes',required=True,type=int);p.add_argument('--output',required=True);a=p.parse_args();report=inspect(a.model,a.expected_bytes);write_report(a.output,report);print(json.dumps(report,sort_keys=True))
