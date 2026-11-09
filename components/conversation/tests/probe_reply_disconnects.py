"""Local socket/pipe disconnect fixtures, using one saved native reply as data."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from reply_framing import FramingError,JsonLineFrames


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    database=a.database.resolve(strict=True);wal=Path(str(database)+'-wal')
    if wal.exists() and wal.stat().st_size:raise ValueError('Closed checkpoint DB required')
    before_hash=hashlib.sha256(database.read_bytes()).hexdigest()
    db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    try:
        rows=[dict(r) for r in db.execute('SELECT session_id,request_id,expected_revision,payload,response FROM requests WHERE status="committed"')]
        row=next(r for r in rows if json.loads(r['response']).get('package_state',{}).get('data_admitted') is True)
        session=dict(db.execute('SELECT id,revision,history,pending FROM sessions WHERE id=?',(row['session_id'],)).fetchone())
    finally:db.close()
    packet=json.loads(row['response']);encoded=(json.dumps(packet,ensure_ascii=False)+'\n').encode()
    request=dict(api_version=2,op='turn',session_id=row['session_id'],request_id=row['request_id'],
                 expected_revision=row['expected_revision'],**json.loads(row['payload']))
    snap=dict(api_version=2,status='snapshot',session_id=session['id'],revision=session['revision'],
              history=json.loads(session['history']),pending=session['pending'])
    checks={};records=[]
    def fresh():
        state=DesktopDraft(request['text']);state.begin(request,confirmed=True);state.edit('Unsent disconnect fixture draft.')
        return state,state.create_reply_receiver()
    def record(name,state,receiver,**extra):
        view=state.view();diagnostic=receiver.view()
        checks[name+'/draft_and_no_automatic_requests']=(view['draft']=='Unsent disconnect fixture draft.'
            and not diagnostic['automatic_requests'] and not diagnostic['connection_authenticated'])
        records.append(dict(case=name,view=view,receiver=diagnostic,**extra))
    # No LF, ending within UTF-8: EOF must not manufacture a packet.
    state,receiver=fresh();local,peer=socket.socketpair();local.settimeout(2)
    try:
        peer.sendall(b'{"text":"\xf0\x9f');peer.shutdown(socket.SHUT_WR)
        while True:
            chunk=local.recv(3)
            if not chunk:break
            receiver.feed(chunk)
        failed=False
        try:receiver.eof()
        except FramingError:failed=True
        checks['partial_utf8_eof/rejected']=(failed and state.view()['active']['reply'] is None
            and receiver.view()['framing']['buffered_bytes']==0 and state.view()['needs_snapshot'])
        record('partial_utf8_eof',state,receiver,synthetic_payload=True)
    finally:local.close();peer.close()
    # A complete reply remains visible when a subsequent frame is cut off.
    state,receiver=fresh();local,peer=socket.socketpair();local.settimeout(2);accepted=None
    try:
        peer.sendall(encoded+b'{"unfinished":');peer.shutdown(socket.SHUT_WR)
        while True:
            chunk=local.recv(31)
            if not chunk:break
            receiver.feed(chunk)
            if receiver.view()['frames_delivered'] and accepted is None:
                state.receive_snapshot(snap);state.set_provenance_details_visible(True);accepted=copy.deepcopy(state.view())
        failed=False
        try:receiver.eof()
        except FramingError:failed=True
        after=state.view()
        checks['complete_then_partial_eof/preserved']=(failed and accepted is not None and not accepted['needs_snapshot']
            and after['active']['reply']==accepted['active']['reply'] and after['active']['transcript']==accepted['active']['transcript']
            and after['needs_snapshot'] and after['active']['guidance']['code']=='reply_stream_ended')
        record('complete_then_partial_eof',state,receiver,synthetic_trailing_frame=True)
    finally:local.close();peer.close()
    # Caller timeout is an explicit error notification, not EOF or an internal timer.
    state,receiver=fresh();local,peer=socket.socketpair();local.settimeout(.02)
    try:
        peer.sendall(b'{');receiver.feed(local.recv(16));primary=None
        try:local.recv(16)
        except TimeoutError as error:primary=error;receiver.transport_failed(error)
        checks['caller_timeout/failed_and_cleared']=(primary is not None and receiver.view()['failure_type']=='TimeoutError'
            and receiver.view()['framing']['buffered_bytes']==0 and state.view()['active']['reply'] is None)
        record('caller_timeout',state,receiver,synthetic_payload=True,caller_timeout_seconds=.02)
    finally:local.close();peer.close()
    # Delayed old EOF and delayed old bytes must not touch a new attempt.
    state,old=fresh();old_eof=state.create_reply_receiver();local,peer=socket.socketpair();local.settimeout(2)
    try:
        peer.sendall(encoded);peer.shutdown(socket.SHUT_WR)
        state.receive_snapshot(snap);state.review_and_release(confirmed=True)
        state.edit(request['text']);state.begin(request,confirmed=True);state.edit('Unsent disconnect fixture draft.')
        state.receive_snapshot(snap);new_before=copy.deepcopy(state.view());stale_rejected=False
        try:
            while True:
                chunk=local.recv(31)
                if not chunk:old.eof();break
                old.feed(chunk)
        except ValueError:stale_rejected=True
        old_eof.eof()
        checks['stale_old_stream/new_attempt_unchanged']=(stale_rejected and state.view()==new_before and not state.view()['needs_snapshot'])
        record('stale_old_stream',state,old,adversarial_reused_identity_fixture=True)
    finally:local.close();peer.close()
    # Actual abortive TCP close only after the complete packet has been accepted.
    state,receiver=fresh();listener=socket.socket();local=None;peer=None;worker=None;ready=threading.Event();errors=[];accepted=None
    try:
        listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
        local=socket.create_connection(listener.getsockname(),timeout=2);peer,_=listener.accept()
        def reset_peer():
            try:
                peer.sendall(encoded)
                if not ready.wait(2):raise TimeoutError('Fixture acceptance handshake')
                peer.sendall(b'{"cut":');peer.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));peer.close()
            except BaseException as error:errors.append(type(error).__name__)
        worker=threading.Thread(target=reset_peer,daemon=True);worker.start();reset=None
        while True:
            try:chunk=local.recv(31)
            except ConnectionResetError as error:reset=error;receiver.transport_failed(error);break
            if not chunk:break
            receiver.feed(chunk)
            if receiver.view()['frames_delivered'] and accepted is None:
                state.receive_snapshot(snap);state.set_provenance_details_visible(True);accepted=copy.deepcopy(state.view());ready.set()
        worker.join(timeout=2);after=state.view()
        checks['complete_then_tcp_reset/preserved']=(reset is not None and errors==[] and not worker.is_alive()
            and accepted is not None and after['active']['reply']==accepted['active']['reply']
            and after['active']['transcript']==accepted['active']['transcript'] and after['needs_snapshot']
            and receiver.view()['failure_type']=='ConnectionResetError' and receiver.view()['framing']['buffered_bytes']==0)
        record('complete_then_tcp_reset',state,receiver,synthetic_trailing_frame=True,transport='localhost TCP abortive close')
    finally:
        ready.set()
        if local is not None:local.close()
        if peer is not None:peer.close()
        listener.close()
        if worker is not None:worker.join(timeout=2)
    # Real pipe input reaches the byte cap without an unbounded pending buffer.
    state,receiver=fresh();read_fd,write_fd=os.pipe();errors=[];payload=b'x'*(JsonLineFrames.max_frame_bytes+1)
    def pipe_peer():
        try:
            offset=0
            while offset<len(payload):offset+=os.write(write_fd,payload[offset:offset+4096])
        except BrokenPipeError:pass  # Reader may stop immediately on its cap.
        except BaseException as error:errors.append(type(error).__name__)
        finally:os.close(write_fd)
    worker=threading.Thread(target=pipe_peer,daemon=True);worker.start();maximum=0;failed=False;received_bytes=0
    try:
        while True:
            chunk=os.read(read_fd,8192)
            if not chunk:break
            received_bytes+=len(chunk)
            try:receiver.feed(chunk)
            except FramingError:failed=True;break
            maximum=max(maximum,receiver.view()['framing']['buffered_bytes'])
    finally:os.close(read_fd);worker.join(timeout=2)
    checks['pipe_limit/bounded_and_failed']=(failed and received_bytes==len(payload) and maximum<=JsonLineFrames.max_frame_bytes and not worker.is_alive()
        and errors==[] and receiver.view()['framing']['buffered_bytes']==0 and state.view()['active']['reply'] is None)
    record('pipe_limit',state,receiver,synthetic_payload=True,max_observed_buffer_bytes=maximum,received_bytes=received_bytes)
    checks['database_bytes_unchanged']=hashlib.sha256(database.read_bytes()).hexdigest()==before_hash
    source=Path(__file__).resolve().parents[1]
    paths=[source/name for name in ('reply_framing.py','desktop_draft.py','desktop_reply.py','desktop_provenance.py',
        'desktop_diagnostics.py','client_diagnostics.py','package_reply_view.py')]+[Path(__file__).resolve()]
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,input_database_sha256=before_hash,
        source_hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        transport_executed=True,transports=['local AF_UNIX socketpair','localhost TCP','OS pipe'],
        fixture_peer=True,synthetic_faults=True,connection_authenticated=False,requests_dispatched=False,
        service_executed=False,native_runtime_rerun=False,graphical_ui_tested=False,executed_actions=0)
    (a.output/'cases.json').write_text(json.dumps(records,indent=2)+'\n');(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
