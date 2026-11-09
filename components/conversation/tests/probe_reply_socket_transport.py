"""Real local socket pairs carry saved reply fixtures; not a real Roko service."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    database=a.database.resolve(strict=True);wal=Path(str(database)+'-wal')
    if wal.exists() and wal.stat().st_size:raise ValueError('Closed evidence DB required')
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    try:
        rows=[dict(row) for row in db.execute('SELECT session_id,request_id,expected_revision,payload,status,response FROM requests ORDER BY session_id,expected_revision')]
        sessions={row['id']:dict(row) for row in db.execute('SELECT id,revision,history,pending FROM sessions')}
    finally:db.close()
    checks={'four_saved_responses':len(rows)==4};views=[]
    for row in rows:
        if row['status']!='committed':raise ValueError('Committed saved reply required')
        packet=json.loads(row['response']);original=dict(api_version=2,op='turn',session_id=row['session_id'],
            request_id=row['request_id'],expected_revision=row['expected_revision'],**json.loads(row['payload']))
        state=DesktopDraft(original['text']);state.begin(original,confirmed=True);state.edit('Unsent socket test draft.')
        receiver=state.create_reply_receiver();encoded=(json.dumps(packet,ensure_ascii=False)+'\n').encode()
        local,peer=socket.socketpair();errors=[];peer_sends=[];read_sizes=[]
        def producer():
            try:
                for start in range(0,len(encoded),9):
                    chunk=encoded[start:start+9];peer.sendall(chunk);peer_sends.append(len(chunk))
                peer.shutdown(socket.SHUT_WR)
            except BaseException as error:errors.append(type(error).__name__)
        worker=threading.Thread(target=producer,daemon=True);worker.start();local.settimeout(5)
        before_eof=None;outbound_absent=False;label=row['session_id']+'/'+row['request_id']
        try:
            while True:
                chunk=local.recv(31)
                if not chunk:receiver.eof();break
                read_sizes.append(len(chunk));receiver.feed(chunk)
                if receiver.view()['frames_delivered'] and before_eof is None:
                    saved=sessions[row['session_id']]
                    state.receive_snapshot(dict(api_version=2,status='snapshot',session_id=row['session_id'],
                        revision=saved['revision'],history=json.loads(saved['history']),pending=saved['pending']))
                    state.set_provenance_details_visible(True);before_eof=state.view()
            worker.join(timeout=2);peer.setblocking(False)
            try:peer.recv(1)
            except BlockingIOError:outbound_absent=True
            after=state.view();diagnostics=receiver.view()
            checks[label+'/actual_fragmented_socket_delivery']=(len(read_sizes)>1 and sum(read_sizes)==len(encoded)
                and sum(peer_sends)==len(encoded) and errors==[] and not worker.is_alive())
            checks[label+'/one_complete_saved_reply']=(diagnostics['frames_delivered']==1
                and after['active']['reply']['request_id']==packet['request_id'])
            checks[label+'/no_client_application_writes']=outbound_absent
            checks[label+'/eof_requires_fresh_snapshot']=(before_eof is not None and not before_eof['needs_snapshot']
                and after['needs_snapshot'] and after['active']['available_actions']==['snapshot']
                and after['active']['guidance']['code']=='reply_stream_ended')
            checks[label+'/reply_and_history_preserved']=(after['active']['reply']==before_eof['active']['reply']
                and after['active']['transcript']==before_eof['active']['transcript'])
            checks[label+'/unsent_draft_and_limits_preserved']=(after['draft']=='Unsent socket test draft.'
                and after['outcome']=='not_established' and not after['active']['reply']['mutation_authority'])
            checks[label+'/closed_does_not_mean_authenticated_or_live']=(diagnostics['state']=='closed'
                and not diagnostics['connection_authenticated'] and not diagnostics['live_host_state_established']
                and not diagnostics['automatic_requests'])
            views.append(dict(identity=label,read_chunk_sizes=read_sizes,peer_send_sizes=peer_sends,
                              before_eof=before_eof,after_eof=after,receiver=diagnostics))
        finally:
            local.close();peer.close();worker.join(timeout=2)
    checks['database_bytes_unchanged']=hashlib.sha256(database.read_bytes()).hexdigest()==before
    source=Path(__file__).resolve().parents[1]
    paths=[source/name for name in ('reply_framing.py','desktop_draft.py','desktop_reply.py','desktop_provenance.py','package_reply_view.py','desktop_diagnostics.py','client_diagnostics.py')]+[Path(__file__).resolve()]
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,input_database_sha256=before,
        source_hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        transport_executed=True,transport_kind='local AF_UNIX socketpair with saved-response fixture peer',
        requests_dispatched=False,service_executed=False,native_runtime_rerun=False,graphical_ui_tested=False,
        connection_authenticated=False,executed_actions=0)
    (a.output/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
