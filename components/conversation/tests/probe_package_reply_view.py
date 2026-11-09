"""Render saved native replies; explicitly NOT a rerun of their native runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_reply_view import render_reply,receipt_notice,LIMITS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--native-result',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    raw=a.native_result.read_bytes();native=json.loads(raw)
    if native['status']!='passed' or not all(native['checks'].values()):raise ValueError('Expected passed native input')
    replies=native['replies']+[native['expired_reply']]
    before=json.dumps(replies,sort_keys=True)
    views=[render_reply(row) for row in replies]
    cli=Path(__file__).resolve().parents[1]/'package_reply_view.py'
    result=subprocess.run([sys.executable,'-B',str(cli)],input=''.join(json.dumps(row)+'\n' for row in replies),
        capture_output=True,text=True,timeout=10,check=True)
    notices=[receipt_notice(row) for row in replies]
    checks={
        'four_saved_native_replies':len(replies)==4,
        'cli_matches_read_only_view':result.stdout==''.join(view+'\n' for view in views) and result.stderr=='',
        'no_input_mutation':json.dumps(replies,sort_keys=True)==before,
        'all_provenance_presentable':all('provenance could not be presented' not in n for n in notices),
        'all_deny_live_authority':all(LIMITS in n for n in notices),
        'missing_not_package_absence':'package absence is not established' in notices[0],
        'available_unknown_observation_age':'observation age unknown' in notices[1] and 'revision 3' in notices[1],
        'historical_not_current':'Historical last-known source (not current evidence)' in notices[2],
        'expired_not_observation_age':'not the source observation age' in notices[3],
        'model_text_labeled_advisory':all('Generated answer (package claims are advisory):' in v for v in views),
        'repeated_render_is_identical':[render_reply(row) for row in replies]==views,
    }
    (a.output/'views.txt').write_text('\n\n---\n\n'.join(views)+'\n')
    (a.output/'native-input.json').write_bytes(raw)
    receipt={'status':'passed' if all(checks.values()) else 'failed','checks':checks,
        'input_native_result_sha256':hashlib.sha256(raw).hexdigest(),'source_hashes':{
            str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (cli,Path(__file__).resolve())},
        'native_runtime_rerun':False,'graphical_ui_tested':False,'executed_actions':0,
        'limitations':['Presenter does not authenticate the transport/producer or recheck files.',
            'Generated prose is labeled advisory; arbitrary unsupported language is not detected or suppressed.']}
    (a.output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
