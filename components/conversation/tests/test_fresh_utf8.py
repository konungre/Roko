"""Native-byte handling with a fake subprocess; real SQLite durable replay."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conversation
import durable_api as api
import fresh


def provider():
    value = fresh.FreshProvider.__new__(fresh.FreshProvider)
    value.profile = {'python':sys.executable, 'infer':'/fake/infer'}
    value.fd = 0
    value.receipts = []
    value.max_tokens = 64
    value.allow_partial = False
    value.verify_model = Mock()
    return value


def native(raw, reason='length'):
    generation = {'input_tokens':20, 'output_tokens':1, 'finish_reason':reason}
    stderr = ('ROKO_GENERATION '+json.dumps(generation)+'\ndescendants_cleaned=1\n').encode()
    process = Mock(pid=12345, returncode=0)
    process.communicate.return_value = (raw, stderr)
    return process, generation


class FreshUtf8Tests(unittest.TestCase):
    def run_provider(self, raw, reason='length', partial=True):
        value = provider()
        value.allow_partial = partial
        process, generation = native(raw, reason)
        return value, process, generation

    def assert_raw(self, receipt, raw):
        self.assertEqual(base64.b64decode(receipt['stdout_base64']), raw)
        self.assertEqual(receipt['stdout_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['stdout_bytes'], len(raw))

    def test_trailing_incomplete_codepoint_is_explicit_and_preserves_metadata(self):
        for raw, expected in [(b'\xe2\n','\ufffd\n'), (b'Hello \xf0\x9f\x8c\n','Hello \ufffd\n'),
                              (b'Hello \xc3','Hello \ufffd')]:
            with self.subTest(raw=raw):
                value, process, generation = self.run_provider(raw)
                with patch.object(fresh.subprocess, 'Popen', return_value=process):
                    self.assertEqual(value.chat([{'role':'user','content':'Hi'}]), expected)
                self.assertEqual(value.last_generation, generation)
                self.assertEqual(set(value.last_generation), {'input_tokens','output_tokens','finish_reason'})
                receipt = value.receipts[-1]
                self.assert_raw(receipt, raw)
                self.assertEqual(receipt['stdout_encoding']['status'], 'incomplete_suffix_replaced')
                self.assertTrue(receipt['model_verified_before_history_commit'])

    def test_valid_utf8_is_unchanged(self):
        raw = 'A lighthouse 🌊\n'.encode()
        value, process, generation = self.run_provider(raw, reason='eos')
        with patch.object(fresh.subprocess, 'Popen', return_value=process):
            self.assertEqual(value.chat([{'role':'user','content':'Hi'}]), raw.decode())
        self.assertEqual(value.receipts[-1]['stdout_encoding']['status'], 'valid')
        self.assert_raw(value.receipts[-1], raw)

    def test_invalid_interior_overlong_surrogate_and_eos_suffix_are_rejected(self):
        for raw, reason in [(b'a\xffb\n','length'), (b'\xe2x\n','length'),
                            (b'\xc0\x80\n','length'), (b'\xed\xa0\n','length'),
                            (b'\xe2\n','eos'), (b'\xe2\n\n','length')]:
            with self.subTest(raw=raw, reason=reason):
                value, process, generation = self.run_provider(raw, reason)
                with patch.object(fresh.subprocess, 'Popen', return_value=process):
                    with self.assertRaisesRegex(fresh.GenerationError, 'invalid_output_encoding'):
                        value.chat([{'role':'user','content':'Hi'}])
                self.assertEqual(value.last_generation, generation)
                self.assertEqual(value.last_error, 'invalid_output_encoding')
                self.assert_raw(value.receipts[-1], raw)
                self.assertEqual(value.receipts[-1]['stdout_encoding']['status'], 'invalid')

    def test_v1_limit_failure_never_commits(self):
        value, process, generation = self.run_provider(b'\xe2\n', partial=False)
        session = conversation.Session(value, None)
        session.prepare({'text':'Hi','context':[]})
        with patch.object(fresh.subprocess, 'Popen', return_value=process):
            with self.assertRaisesRegex(fresh.GenerationError, 'output_limit'):
                session.infer([session.user_message()])
        self.assertEqual(value.last_generation, generation)
        self.assertEqual(value.last_error, 'output_limit')
        self.assertEqual(session.history, [])
        self.assertIsNone(session.reply)

    def test_generation_is_parsed_before_bad_stdout(self):
        value = provider()
        process = Mock(pid=12345, returncode=0)
        process.communicate.return_value = (b'\xe2\n', b'descendants_cleaned=1\n')
        with patch.object(fresh.subprocess, 'Popen', return_value=process):
            with self.assertRaisesRegex(fresh.GenerationError, 'missing_generation_receipt'):
                value.chat([{'role':'user','content':'Hi'}])
        self.assert_raw(value.receipts[-1], b'\xe2\n')
        self.assertEqual(value.last_error, 'missing_generation_receipt')

    def test_v2_partial_commits_and_replays_after_restart_without_inference(self):
        previous = conversation.session
        globals_before = {name:getattr(api,name) for name in ('store','current','immediate','completed')}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'ROKO_HISTORY_DB':str(Path(temp)/'history.sqlite')}):
            try:
                for name in globals_before: setattr(api,name,None)
                value, process, generation = self.run_provider(b'\xe2\n')
                api.initialize(value, None)
                request = json.dumps({'api_version':2,'op':'turn','session_id':'s','request_id':'r',
                    'expected_revision':0,'text':'Hi','context':[],'max_output_tokens':1})
                with patch.object(fresh.subprocess, 'Popen', return_value=process) as spawn:
                    self.assertTrue(api.prepare_line(request))
                    session = conversation.session
                    messages = session.history + [session.user_message()]
                    assistant = session.infer(messages)
                    saved = json.loads(session.commit(messages+[assistant]))
                    self.assertEqual(saved['status'], 'truncated')
                    self.assertEqual(saved['text'], '\ufffd\n')
                    self.assertEqual(saved['generation'], generation)
                    self.assertEqual(saved['revision'], 1)
                    self.assertEqual(api.store.snapshot('s')['history'][-1]['content'], '\ufffd\n')
                    api.store.close()
                    api.initialize(provider(), None)
                    self.assertFalse(api.prepare_line(request))
                    self.assertEqual(json.loads(api.immediate_json()), saved)
                    self.assertEqual(spawn.call_count, 1)
            finally:
                if api.store: api.store.close()
                for name, old in globals_before.items(): setattr(api,name,old)
                conversation.session = previous


if __name__ == '__main__': unittest.main()
