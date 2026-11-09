"""Native MORK boundary for embedded Janus; real work runs in standalone Python."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[2]/'mork-recovery-v1/source'
sys.path.insert(0,str(SOURCE))
import native_mork
from rebuilt_mork import RebuiltMORKCandidate


class ExternalMORKBackend:
    def __init__(self, profile):
        self.python = profile['python']
        self.config = dict(profile['durable_memory'])
        # Verify explicitly selected bytes before any request can reach launch.
        RebuiltMORKCandidate(self.config['manifest'],
            expected_manifest_sha256=self.config['manifest_sha256'],python_executable=self.python)

    def query_facts(self, facts, query, *, timeout=3):
        facts,query = native_mork._validate(facts,query,timeout)
        source = Path(__file__).resolve().parent
        stamp = Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
        command = [self.python,'-B',str(source/'mork_supervise.py'),
            '--parent-pid',str(os.getpid()),'--parent-start',stamp,'--seconds',str(timeout+8),'--',
            self.python,'-B',str(source/'mork_host.py'),'--manifest',self.config['manifest'],
            '--manifest-sha256',self.config['manifest_sha256'],'--python',self.python]
        proc = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,start_new_session=True,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'})
        try:
            out,err = proc.communicate(json.dumps({'facts':facts,'query':query,'timeout':timeout},
                                                  separators=(',',':')).encode('ascii'),timeout=timeout+15)
        except BaseException:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            raise
        if proc.returncode or len(out)>8192 or len(err)>16384 or b'descendants_cleaned=1' not in err:
            raise native_mork.NativeMORKError('Standalone MORK supervision failed; no memory returned')
        result = json.loads(out)
        if (result.get('implementation')!='native-mork-rebuild-bounded-facts' or
                result.get('runtime_manifest_sha256')!=self.config['manifest_sha256'] or
                result.get('authorizes_actions') is not False):
            raise native_mork.NativeMORKError('Standalone MORK receipt mismatch')
        return {**result,'outer_supervisor':'standalone-python-subreaper','descendants_cleaned':True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--python',required=True)
    args = parser.parse_args()
    data = sys.stdin.buffer.read(native_mork.MAX_REQUEST_BYTES+129)
    if len(data)>native_mork.MAX_REQUEST_BYTES+128:raise ValueError('Native host request cap')
    request = json.loads(data)
    if type(request) is not dict or set(request)!={'facts','query','timeout'}:
        raise ValueError('Native host request schema')
    runtime = RebuiltMORKCandidate(args.manifest,expected_manifest_sha256=args.manifest_sha256,
                                   python_executable=args.python)
    print(json.dumps(runtime.query_facts(request['facts'],request['query'],timeout=request['timeout'])))


if __name__ == '__main__':main()
