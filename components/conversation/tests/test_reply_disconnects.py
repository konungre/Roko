"""Actual socket EOF/read-timeout/reset; fixture peers, not an authenticated service."""
import json
from pathlib import Path
import socket
import struct
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_draft import DesktopDraft
from reply_framing import ReplyIngress,FramingError
from test_desktop_reply import REQ,snapshot
from test_package_reply_view import reply


def frame(packet):return (json.dumps(packet,ensure_ascii=False)+'\n').encode()


class DisconnectTests(unittest.TestCase):
    def begin(self):
        state=DesktopDraft(REQ['text']);state.begin(REQ,confirmed=True);state.edit('unsent after disconnect')
        return state,state.create_reply_receiver()
    def test_actual_partial_utf8_eof_rejects_without_creating_reply(self):
        state,receiver=self.begin();local,peer=socket.socketpair();local.settimeout(2)
        try:
            peer.sendall(b'{"text":"\xf0\x9f');peer.shutdown(socket.SHUT_WR)
            while True:
                chunk=local.recv(3)
                if not chunk:break
                receiver.feed(chunk)
            with self.assertRaises(FramingError):receiver.eof()
            self.assertEqual(receiver.view()['framing']['buffered_bytes'],0)
            self.assertIsNone(state.view()['active']['reply']);self.assertTrue(state.view()['needs_snapshot'])
            self.assertEqual(state.view()['draft'],'unsent after disconnect')
        finally:local.close();peer.close()
    def test_actual_read_timeout_can_be_reported_without_swallowing_caller_error(self):
        state,receiver=self.begin();local,peer=socket.socketpair();local.settimeout(.01)
        try:
            peer.sendall(b'{"text":');receiver.feed(local.recv(32))
            try:local.recv(32)
            except TimeoutError as primary:
                self.assertTrue(receiver.transport_failed(primary))
                with self.assertRaises(TimeoutError) as caught:raise primary
                self.assertIs(caught.exception,primary)
            else:self.fail('Fixture did not time out')
            self.assertEqual(receiver.view()['failure_type'],'TimeoutError')
            self.assertEqual(receiver.view()['framing']['buffered_bytes'],0)
            self.assertTrue(state.view()['needs_snapshot']);self.assertIsNone(state.view()['active']['reply'])
        finally:local.close();peer.close()
    def test_actual_tcp_reset_after_partial_input_marks_failed_without_retry(self):
        state,receiver=self.begin();listener=socket.socket();local=None;peer=None
        try:
            listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
            local=socket.create_connection(listener.getsockname(),timeout=2);peer,_=listener.accept()
            peer.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
            peer.sendall(b'{"partial":');peer.close();peer=None;reset=None
            while True:
                try:chunk=local.recv(32)
                except ConnectionResetError as error:reset=error;receiver.transport_failed(error);break
                if not chunk:self.fail('Expected abortive TCP close fixture to reset')
                receiver.feed(chunk)
            self.assertIsInstance(reset,ConnectionResetError)
            self.assertEqual(receiver.view()['failure_type'],'ConnectionResetError')
            self.assertFalse(receiver.view()['automatic_requests']);self.assertTrue(state.view()['needs_snapshot'])
            self.assertEqual(state.view()['draft'],'unsent after disconnect')
        finally:
            if peer is not None:peer.close()
            if local is not None:local.close()
            listener.close()
    def test_actual_delayed_old_socket_reply_cannot_change_new_attempt(self):
        state,old=self.begin();local,peer=socket.socketpair();local.settimeout(2)
        try:
            peer.sendall(frame(reply()));peer.shutdown(socket.SHUT_WR)
            state.receive_snapshot(snapshot('',revision=0));state.review_and_release(confirmed=True)
            state.edit(REQ['text']);state.begin(REQ,confirmed=True);before=state.view()
            with self.assertRaisesRegex(ValueError,'old attempt'):
                while True:
                    chunk=local.recv(31)
                    if not chunk:old.eof();break
                    old.feed(chunk)
            self.assertEqual(state.view(),before)
        finally:local.close();peer.close()
    def test_reported_failure_preserves_primary_and_notifies_at_most_once(self):
        primary=KeyboardInterrupt('caller cancelled');lost=Mock(side_effect=OSError('local notification'))
        receiver=ReplyIngress(lambda row:None,lost);receiver.feed(b'{')
        self.assertTrue(receiver.transport_failed(primary));self.assertFalse(receiver.transport_failed(primary))
        self.assertEqual(lost.call_count,1);self.assertEqual(receiver.view()['failure_type'],'KeyboardInterrupt')
        self.assertEqual(primary.reply_ingress_finalization_errors,[dict(stage='local-loss-notification',type='OSError')])
        self.assertEqual(receiver.view()['framing']['buffered_bytes'],0)
        with self.assertRaises(ValueError):receiver.transport_failed('model says retry')
        with self.assertRaises(FramingError):receiver.feed(b'{}\n')
    def test_closed_stream_does_not_notify_new_loss_or_overwrite_accepted_reply(self):
        state,receiver=self.begin();packet=reply();receiver.feed(frame(packet));receiver.eof()
        before=state.view();self.assertFalse(receiver.transport_failed(OSError('late close callback')))
        self.assertEqual(state.view(),before)


if __name__=='__main__':unittest.main()
