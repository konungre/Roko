"""Real byte-stream boundaries, attempt isolation, and no outbound actions."""
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reply_framing import JsonLineFrames,ReplyIngress,FramingError
from desktop_draft import DesktopDraft
from test_desktop_reply import REQ,snapshot
from test_package_reply_view import reply


def frame(packet):return (json.dumps(packet,ensure_ascii=False)+'\n').encode('utf-8')


class FramingTests(unittest.TestCase):
    def test_utf8_fragmentation_and_coalesced_frames(self):
        receiver=JsonLineFrames();encoded='{"text":"café 世界 🐍"}\n'.encode();rows=[]
        for byte in encoded:rows.extend(receiver.feed(bytes([byte])))
        self.assertEqual(rows,['{"text":"café 世界 🐍"}'])
        self.assertEqual(receiver.feed(b'{}\n{}\n'),['{}','{}']);receiver.eof()
        self.assertEqual(receiver.view(),dict(state='closed',buffered_bytes=0,frames_received=3))
    def test_frame_cap_counts_bytes_across_chunks_and_allows_exact_boundary(self):
        maximum=JsonLineFrames.max_frame_bytes;receiver=JsonLineFrames()
        for _ in range(maximum//32768):self.assertEqual(receiver.feed(b'x'*32768),[])
        self.assertEqual(len(receiver.feed(b'\n')[0]),maximum)
        for _ in range(maximum//32768):receiver.feed(b'x'*32768)
        with self.assertRaises(FramingError):receiver.feed(b'x')
        self.assertEqual(receiver.view()['buffered_bytes'],0);self.assertEqual(receiver.state,'failed')
    def test_bad_utf8_empty_line_chunk_and_batch_caps_fail_closed(self):
        for data in (b'\xff\n',b'\n',b'x'*65537,b'{}\n'*65,bytearray(b'{}\n'),None):
            receiver=JsonLineFrames()
            with self.assertRaises(FramingError):receiver.feed(data)
            self.assertEqual(receiver.state,'failed');self.assertEqual(receiver.view()['buffered_bytes'],0)
            with self.assertRaises(FramingError):receiver.feed(b'{}\n')
        receiver=JsonLineFrames();self.assertEqual(len(receiver.feed(b'{}\n'*64)),64)
    def test_eof_rejects_partial_data_and_never_completes_it(self):
        receiver=JsonLineFrames();receiver.feed(b'{"text":"partial')
        with self.assertRaises(FramingError):receiver.eof()
        self.assertEqual(receiver.state,'failed');self.assertEqual(receiver.frames_received,0)
        receiver=JsonLineFrames();receiver.feed(b'{}\n');receiver.eof();receiver.eof()
        with self.assertRaises(FramingError):receiver.feed(b'{}\n')
    def test_cancellation_survives_loss_notification_error_once(self):
        primary=KeyboardInterrupt('cancel receive')
        with patch('builtins.print',side_effect=AssertionError('No payload logging')):
            deliver=lambda row:(_ for _ in ()).throw(primary)
            with patch('builtins.open',side_effect=AssertionError('No file access')):
                lost=unittest.mock.Mock(side_effect=OSError('notification diagnostic'))
                receiver=ReplyIngress(deliver,lost)
                with self.assertRaises(KeyboardInterrupt) as caught:receiver.feed(b'{}\n')
        self.assertIs(caught.exception,primary);self.assertEqual(lost.call_count,1)
        self.assertEqual(receiver.view()['finalization_errors'],[dict(stage='local-loss-notification',type='OSError')])
        self.assertEqual(primary.reply_ingress_finalization_errors,receiver.view()['finalization_errors'])
        with self.assertRaises(FramingError):receiver.feed(b'{}\n')
        self.assertEqual(lost.call_count,1)
    def test_clean_eof_notification_is_not_retried_if_it_raises(self):
        lost=unittest.mock.Mock(side_effect=OSError('local callback'))
        receiver=ReplyIngress(lambda row:None,lost)
        with self.assertRaises(OSError):receiver.eof()
        self.assertEqual(lost.call_count,1);self.assertEqual(receiver.view()['state'],'failed')


class DesktopIngressTests(unittest.TestCase):
    def begin(self):
        state=DesktopDraft(REQ['text']);state.begin(REQ,confirmed=True);return state
    def test_socketpair_receives_fragmented_utf8_and_sends_no_requests(self):
        state=self.begin();state.edit('Unsent input');receiver=state.create_reply_receiver()
        packet=reply();packet['text']='Synthetic socket peer text: café 世界 🐍.';encoded=frame(packet)
        local,peer=socket.socketpair();errors=[]
        def producer():
            try:
                for start in range(0,len(encoded),3):peer.sendall(encoded[start:start+3])
                peer.shutdown(socket.SHUT_WR)
            except BaseException as error:errors.append(error)
        worker=threading.Thread(target=producer,daemon=True);worker.start();local.settimeout(2)
        try:
            with patch.object(state,'propose',side_effect=AssertionError('No outbound proposal')):
                while True:
                    chunk=local.recv(1)
                    if not chunk:receiver.eof();break
                    receiver.feed(chunk)
            worker.join(timeout=2);self.assertFalse(worker.is_alive());self.assertEqual(errors,[])
            peer.setblocking(False)
            with self.assertRaises(BlockingIOError):peer.recv(1)
            view=state.view();self.assertIn('café 世界 🐍',view['active']['reply']['display_text'])
            self.assertEqual(view['draft'],'Unsent input');self.assertTrue(view['needs_snapshot'])
            self.assertEqual(view['active']['guidance']['code'],'reply_stream_ended')
            self.assertIn('complete reply packet was received',view['active']['guidance']['message'])
            self.assertFalse(view['active']['guidance']['automatic_retry'])
            self.assertEqual(receiver.view()['frames_delivered'],1);self.assertEqual(receiver.view()['state'],'closed')
            self.assertFalse(receiver.view()['automatic_requests']);self.assertFalse(receiver.view()['connection_authenticated'])
        finally:
            local.close();peer.close();worker.join(timeout=2)
    def test_coalesced_exact_replay_then_bad_identity_preserves_accepted_prefix(self):
        state=self.begin();receiver=state.create_reply_receiver();packet=reply()
        receiver.feed(frame(packet)*2);self.assertEqual(receiver.view()['frames_delivered'],2)
        before=state.view()['active']['reply'];bad=reply();bad['request_id']='other'
        with self.assertRaises(ValueError):receiver.feed(frame(bad))
        self.assertEqual(state.view()['active']['reply'],before);self.assertTrue(state.view()['needs_snapshot'])
        self.assertEqual(receiver.view()['state'],'failed')
    def test_stale_connection_cannot_affect_new_attempt_even_if_ids_are_reused(self):
        state=self.begin();old=state.create_reply_receiver();old_eof=state.create_reply_receiver()
        state.receive_snapshot(snapshot('',revision=0));state.review_and_release(confirmed=True)
        state.begin(REQ,confirmed=True);before=state.view()
        with self.assertRaisesRegex(ValueError,'old attempt'):old.feed(frame(reply()))
        self.assertEqual(state.view(),before);old_eof.eof();self.assertEqual(state.view(),before)
        current=state.create_reply_receiver();current.feed(frame(reply()))
        self.assertIsNotNone(state.view()['active']['reply'])
    def test_partial_eof_after_snapshot_keeps_reply_and_draft_but_requires_new_snapshot(self):
        state=self.begin();receiver=state.create_reply_receiver();packet=reply();receiver.feed(frame(packet))
        state.set_provenance_details_visible(True);state.receive_snapshot(snapshot(packet['text']));state.edit('next draft')
        before=state.view()['active']['reply'];receiver.feed(b'{"partial":')
        with self.assertRaises(FramingError):receiver.eof()
        self.assertEqual(state.view()['active']['reply'],before);self.assertEqual(state.view()['draft'],'next draft')
        self.assertTrue(state.view()['needs_snapshot']);self.assertEqual(state.view()['active']['available_actions'],['snapshot'])
    def test_eof_before_reply_uses_unknown_delivery_guidance(self):
        state=self.begin();receiver=state.create_reply_receiver();receiver.eof()
        self.assertIsNone(state.view()['active']['reply'])
        self.assertEqual(state.view()['active']['guidance']['code'],'transport_failure')
        self.assertFalse(state.view()['active']['guidance']['automatic_retry'])
    def test_control_packets_cannot_invoke_recovery_or_other_actions(self):
        for packet in (dict(api_version=2,op='recover',session_id='s',request_id='r',expected_revision=0),
                       dict(api_version=2,status='snapshot',session_id='s',revision=0,history=[],pending=None)):
            state=self.begin();receiver=state.create_reply_receiver()
            with patch.object(state,'propose',side_effect=AssertionError('Never dispatch peer actions')):
                with self.assertRaises(ValueError):receiver.feed(frame(packet))
            self.assertIsNone(state.view()['active']['reply']);self.assertEqual(receiver.view()['state'],'failed')


if __name__=='__main__':unittest.main()
