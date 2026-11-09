"""Development probe only; not the versioned desktop API or a service."""
import argparse,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser(description='Real recovered-host Omega conversation probe; requires inherited network denial')
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
ROOT=args.workspace.resolve(strict=True)
OUT=args.output.resolve()
OUT.mkdir(parents=True,exist_ok=False)
SOURCE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'symbolic-ai-v4/source'))
import gateway
lock=gateway.verify_inputs('541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0',time.monotonic()+60)
if shutil.disk_usage(ROOT).free<4*1024**3 or gateway.available()<7*1024**3:
    raise RuntimeError('Require 4GiB disk / 7GiB available memory startup reserve')
recovered=ROOT/'recovery-second/runtime/swipl-basic/runtime'
swi=recovered/'swipl/lib/swipl'; python=recovered/'recovered-python312'; system=ROOT/'symbolic-ai-v4/system'
lib=':'.join(map(str,(system,python/'lib',swi/'lib/x86_64-linux')))
env=dict(PATH='/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8',PYTHONHOME=str(python),
 PYTHONPATH=str(SOURCE),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=lib,
 SWI_HOME_DIR=str(swi),PETTA_PATH=str(ROOT/'omega-baseline/vendor/PeTTa-omega-release'),
 OMEGA_PATH=str(ROOT/'omega-baseline/vendor/PeTTa/repos/Omega'),ROKO_CONVERSATION_STEP=str(SOURCE/'step.metta'),
 ROKO_RECOVERED_PROFILE=str(ROOT/'omega-baseline/recovery/granite-host-requalification'),
 ROKO_MODEL=str(ROOT/'recovery-second/model/granite-4.0-h-tiny-Q4_K_M.gguf'),
 ROKO_PYTHON=sys.executable,ROKO_SYMBOLIC_ROOT=str(ROOT/'symbolic-ai-v4'))
command=[str(system/'ld-linux-x86-64.so.2'),'--inhibit-cache','--library-path',lib,
 str(swi/'bin/x86_64-linux/swipl'),'--stack-limit=64m','-q','-f','none','--no-packs','-s',str(SOURCE/'worker.pl'),'--','silent']
turns=[{'text':'I am writing a story about a lighthouse but feel stuck. Could you suggest one small next step?','context':[]},
       {'text':'What setting did I mention, and how could that shape the opening?','context':[]}]
source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}
record={'source_hashes':source_hashes,'requests':turns,'status':'started','executed_actions':0}
(OUT/'inputs.json').write_text(json.dumps(record,indent=2))
# The outer process was launched under network denial; children inherit the filter.
process=subprocess.Popen(command,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
try:
    out,err=process.communicate(''.join(json.dumps(t)+'\n' for t in turns).encode(),timeout=330)
except BaseException:
    os.killpg(process.pid,signal.SIGTERM)
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL);process.wait()
    raise
(OUT/'stdout.txt').write_bytes(out);(OUT/'stderr.txt').write_bytes(err)
record.update(returncode=process.returncode,status='completed' if process.returncode==0 else 'failed',
 symbolic_inputs_postverified=bool(gateway.verify_inputs('541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0',time.monotonic()+60)))
(OUT/'result.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record));print(out.decode());print(err.decode()[-2000:]);sys.exit(process.returncode)
