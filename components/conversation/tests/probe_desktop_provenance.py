"""Local disclosure on saved native evidence; no transport, model, or GUI run."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from package_reply_view import LIMITS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frame-input',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    database=a.database.resolve(strict=True);wal=Path(str(database)+'-wal')
    if wal.exists() and wal.stat().st_size:raise ValueError('Closed checkpoint DB required')
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    try:rows=[dict(row) for row in db.execute('SELECT session_id,request_id,expected_revision,payload,status,response FROM requests ORDER BY session_id,expected_revision')]
    finally:db.close()
    checks={'four_saved_replies':len(rows)==4};views=[]
    for row in rows:
        if row['status']!='committed':raise ValueError('Expected committed evidence')
        packet=json.loads(row['response']);payload=json.loads(row['payload'])
        original=dict(api_version=2,op='turn',session_id=row['session_id'],request_id=row['request_id'],
            expected_revision=row['expected_revision'],**payload)
        state=DesktopDraft(original['text']);state.begin(original,confirmed=True)
        def receive(value):
            if a.frame_input:state.receive_reply_line(json.dumps(value)+'\n')
            else:state.receive_reply(value)
        state.edit('Unsent draft remains local.');receive(packet);name=row['session_id']+'/'+row['request_id']
        collapsed=state.view();panel=collapsed['active']['reply'];summary=panel['provenance']['summary_text']
        checks[name+'/collapsed_notice_keeps_uncertainty']=(LIMITS in summary and 'Source observation age: unknown.' in summary
            and 'not observation time' in summary and panel['provenance']['details_text'] is None)
        with patch.object(state,'propose',side_effect=AssertionError('Local disclosure must not propose a request')):
            state.set_provenance_details_visible(True);expanded=state.view()
            state.set_provenance_details_visible(False);again=state.view()
        details=expanded['active']['reply']['provenance']
        checks[name+'/expand_preserves_summary_and_authority_limits']=(details['summary_text']==summary and LIMITS in details['details_text']
            and details['source_check_refreshed'] is False and details['mutation_authority'] is False)
        checks[name+'/only_local_disclosure_fields_change']=(again==collapsed and expanded['draft']==collapsed['draft']
            and expanded['active']['available_actions']==collapsed['active']['available_actions']
            and expanded['active']['transcript']==collapsed['active']['transcript'] and expanded['needs_snapshot']==collapsed['needs_snapshot'])
        state.set_provenance_details_visible(True);state.transport_lost();receive(packet)
        lost=state.view();disclosure=lost['active']['reply']['provenance']
        checks[name+'/loss_and_replay_do_not_refresh_or_unlock']=(lost['needs_snapshot'] and lost['active']['available_actions']==['snapshot']
            and disclosure['details_text']==details['details_text'] and disclosure['details_expanded'] is True)
        source=packet['package_state'].get('source') or packet['package_state'].get('last_known_source')
        checks[name+'/details_match_saved_source_scope']=(('Source commit: '+source['source_commit'] in details['details_text']) if source else 'Source commit:' not in details['details_text'])
        checks[name+'/answer_stays_advisory_and_separate']=(details['answer_text'].startswith('Generated answer (package claims are advisory):')
            and all(not line or line.startswith('  | ') for line in details['answer_text'].split('\n')[1:]))
        if a.frame_input:
            stable=copy.deepcopy(state.view());encoded=json.dumps(packet)
            bad_frames=[encoded[:-1]+',\"package_state\":null}',encoded[:-1]+',\"probe_overflow\":1e999}',
                        encoded[:30],encoded+'\n'+encoded]
            rejected=0
            for frame in bad_frames:
                try:state.receive_reply_line(frame)
                except ValueError:rejected+=1
            checks[name+'/synthetic_ambiguous_frames_rejected_atomically']=(rejected==len(bad_frames) and state.view()==stable)
        views.append({'identity':name,'collapsed':collapsed,'expanded':expanded,'after_loss_and_repeat':lost})
    checks['database_bytes_unchanged']=hashlib.sha256(database.read_bytes()).hexdigest()==before
    source=Path(__file__).resolve().parents[1]
    paths=[source/name for name in ('desktop_provenance.py','desktop_reply.py','desktop_draft.py','desktop_diagnostics.py','package_reply_view.py')]+[Path(__file__).resolve()]
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'input_database_sha256':before,
        'source_hashes':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'requests_reconstructed_from_saved_normalized_payload':True,'frame_input':a.frame_input,
        'synthetic_bad_frame_fixtures':a.frame_input,'native_runtime_rerun':False,
        'graphical_ui_tested':False,'transport_executed':False,'executed_actions':0}
    (a.output/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
