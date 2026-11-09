"""Fixed future native gate worker. Not executed in the source-only test stage.

The controller must verify the frozen manifest and supervise this worker. It
imports only the derived slice, not upstream nace/world/main/bridge modules.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from adapter import transition
import nace_slice

MAX_PACKET = 16384

def main():
    raw = sys.stdin.buffer.read(MAX_PACKET+1)
    if len(raw)>MAX_PACKET:
        raise ValueError('request exceeds packet cap')
    def reject_constant(value):
        raise ValueError('non-finite input constant')
    def unique_pairs(pairs):
        out = {}
        for k,v in pairs:
            if k in out:
                raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    request = json.loads(raw,parse_constant=reject_constant,object_pairs_hook=unique_pairs)
    result = transition(request,nace_slice)
    result['worker_kind']='actual_pinned_nace_function_slice'
    encoded=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(encoded)>MAX_PACKET:
        raise ValueError('response exceeds packet cap')
    sys.stdout.buffer.write(encoded+b'\n')

if __name__=='__main__':
    main()
