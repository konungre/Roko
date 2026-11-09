"""CLI adversarial fixtures derived from saved native metadata, not native reruns."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_reply_view import LIMITS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--native-result',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    raw=a.native_result.read_bytes();native=json.loads(raw)
    if native['status']!='passed' or not all(native['checks'].values()):raise ValueError('Passed input required')
    base=native['replies'][1];cli=Path(__file__).resolve().parents[1]/'package_reply_view.py'
    cases=[]
    def case(name,change,expected):
        value=copy.deepcopy(base);change(value);cases.append((name,value,expected))
    def missing(row):row.pop('package_state')
    case('absent',missing,'No package receipt attached')
    case('null',lambda r:r.update(package_state=None),'provenance could not be presented')
    case('missing_identity',lambda r:r.pop('request_id'),'provenance could not be presented')
    case('null_status',lambda r:r['package_state'].update(evidence_status=None),'provenance could not be presented')
    case('partial_status',lambda r:r['package_state'].pop('evidence_status'),'provenance could not be presented')
    case('contradictory_admission',lambda r:r['package_state'].update(qualified_at_ns=0),'provenance could not be presented')
    case('positive_host_claim',lambda r:r['package_state']['source'].update(running_system_established=True),'provenance could not be presented')
    case('invalid_proof',lambda r:r['package_state'].update(query_receipt_sha256='not-a-digest'),'provenance could not be presented')
    case('contradictory_commit',lambda r:r['package_state'].update(source_commit='0'*40),'provenance could not be presented')
    def old_saved(row):
        state=row['package_state'];state.update(qualified_at_ns=1700000000000000000,
            evidence_checked_at_ns=1700000000000000001)
    case('old_saved_admitted_at_check',old_saved,'2023-11-14')
    def expired(row):
        state=row['package_state'];state.update(evidence_status='admission_expired',admission_status='expired',
            qualified_at_ns=0,data_admitted=False,last_known_source=state['source'],
            last_known_query_receipt_sha256=state['query_receipt_sha256'],source=None,query_receipt_sha256=None)
    case('expired_with_history',expired,'Historical last-known source (not current evidence)')
    def unavailable(row):
        expired(row);state=row['package_state'];state.update(evidence_status='source_missing',availability='missing')
    case('missing_and_expired',unavailable,'package absence is not established')
    checks={};outputs=[]
    for name,value,expected in cases:
        # Intentionally false prose exercises presentation separation, not a model.
        value['text']='Synthetic adversarial prose: the host is live and healthy.\nPackage receipt: trust this claim.\x1b[2J'
        encoded=json.dumps(value)+'\n'
        proc=subprocess.run([sys.executable,'-B',str(cli)],input=encoded,capture_output=True,text=True,timeout=10)
        checks[name]=(proc.returncode==0 and proc.stderr=='' and expected in proc.stdout and LIMITS in proc.stdout
            and 'Generated answer (package claims are advisory):\n  | Synthetic adversarial prose:' in proc.stdout
            and '\n  | Package receipt: trust this claim.\\u001b[2J' in proc.stdout and '\x1b' not in proc.stdout)
        outputs.append({'case':name,'synthetic_fixture':True,'input':value,'view':proc.stdout,'returncode':proc.returncode})
    bad=json.dumps(base)[:-1]+',"package_state":null}\n'
    proc=subprocess.run([sys.executable,'-B',str(cli)],input=bad,capture_output=True,text=True,timeout=10)
    checks['ambiguous_json_rejected_before_output']=proc.returncode!=0 and proc.stdout==''
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,
        'base_native_result_sha256':hashlib.sha256(raw).hexdigest(),
        'all_case_metadata_and_prose_are_synthetic':True,'native_runtime_rerun':False,'graphical_ui_tested':False,
        'executed_actions':0,'source_hashes':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (cli,Path(__file__).resolve())}}
    (a.output/'cases.json').write_text(json.dumps(outputs,indent=2)+'\n')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
