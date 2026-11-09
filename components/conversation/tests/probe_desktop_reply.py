"""Candidate callbacks on saved native DB evidence; no GUI or service execution."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from package_reply_view import LIMITS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    database=a.database.resolve(strict=True);wal=Path(str(database)+'-wal')
    if wal.exists() and wal.stat().st_size:raise ValueError('Closed checkpoint DB required; do not ignore live WAL')
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    try:
        rows=[dict(row) for row in db.execute('SELECT session_id,request_id,expected_revision,payload,status,response FROM requests ORDER BY session_id,expected_revision')]
        sessions={row['id']:dict(row) for row in db.execute('SELECT id,revision,history,pending FROM sessions')}
    finally:db.close()
    checks={'four_saved_replies':len(rows)==4};views=[]
    for row in rows:
        if row['status']!='committed':raise ValueError('Expected saved committed evidence')
        packet=json.loads(row['response']);payload=json.loads(row['payload'])
        original=dict(api_version=2,op='turn',session_id=row['session_id'],request_id=row['request_id'],
                      expected_revision=row['expected_revision'],**payload)
        state=DesktopDraft(original['text']);captured=state.begin(original,confirmed=True)
        state.edit('New unsent draft, never submitted.');state.receive_reply(packet)
        first=state.view();panel=first['active']['reply'];name=row['session_id']+'/'+row['request_id']
        checks[name+'/notice_and_no_host_authority']=(LIMITS in panel['display_text'] and panel['mutation_authority'] is False
            and panel['live_host_state_established'] is False and panel['source_check_refreshed'] is False)
        checks[name+'/reply_not_snapshot']=(first['needs_snapshot'] and panel['history_relation']=='snapshot_unavailable'
            and first['active']['transcript']==[] and first['outcome']=='not_established')
        saved=sessions[row['session_id']]
        snapshot=dict(api_version=2,status='snapshot',session_id=row['session_id'],revision=saved['revision'],
                      history=json.loads(saved['history']),pending=saved['pending'])
        state.receive_snapshot(snapshot);matched=state.view()
        checks[name+'/actual_saved_turn_matches']=(matched['active']['reply']['history_relation']=='matching_snapshot_turn'
            and matched['active']['transcript']==snapshot['history'])
        state.transport_lost();state.receive_reply(packet)
        lost=state.view();blocked=False
        try:state.propose('replay_original',confirmed=True)
        except ValueError:blocked=True
        checks[name+'/lost_service_reply_does_not_enable_replay']=(blocked and lost['needs_snapshot']
            and lost['active']['available_actions']==['snapshot'] and lost['active']['reply']['display_text']==panel['display_text'])
        state.receive_snapshot(snapshot)
        checks[name+'/explicit_replay_proposal_retains_captured_payload']=(state.propose('replay_original',confirmed=True)==captured
            and state.view()['draft']=='New unsent draft, never submitted.' and state.view()['automatic_requests'] is False)
        views.append({'identity':name,'view':state.view(),'saved_reply_not_refreshed':True})
        state.review_and_release(confirmed=True)
        checks[name+'/release_not_history_mutation']=(state.view()['active'] is None and state.view()['draft']=='New unsent draft, never submitted.'
            and state.view()['outcome']=='not_established')
    checks['database_bytes_unchanged']=hashlib.sha256(database.read_bytes()).hexdigest()==before
    source=Path(__file__).resolve().parents[1]
    paths=[source/name for name in ('desktop_reply.py','desktop_draft.py','desktop_diagnostics.py','package_reply_view.py')]+[Path(__file__).resolve()]
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'input_database_sha256':before,
        'source_hashes':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'requests_reconstructed_from_saved_normalized_payload':True,'native_runtime_rerun':False,
        'graphical_ui_tested':False,'transport_executed':False,'executed_actions':0}
    (a.output/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
