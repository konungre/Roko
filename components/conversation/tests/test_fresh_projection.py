"""FreshProvider projection orchestration with explicitly mocked native processes."""
import base64
import contextlib
import hashlib
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conversation
import fresh
import recovered

CLEANUP = b'ROKO_SUPERVISOR reason=native-exit descendants_cleaned=1\n'


def provider(policy='extractive_v1'):
    value = fresh.FreshProvider.__new__(fresh.FreshProvider)
    value.profile = {'python':sys.executable, 'infer':'/fake/infer',
                     'context_projection':'extractive_v1'}
    value.context_policy = policy
    value.token_counter_receipts = []
    value.receipts = []
    value.fd = 0
    value.max_tokens = 64
    value.allow_partial = True
    value.verify_model = Mock()
    return value


def counter(tokens=20, *, raw=None, stderr=CLEANUP, returncode=0):
    process = Mock(pid=12345, returncode=returncode)
    process.communicate.return_value = (
        json.dumps({'input_tokens':tokens}).encode() if raw is None else raw, stderr)
    return process


def generation(tokens=20, *, raw=b'Hello\n', reason='eos'):
    process = Mock(pid=12346, returncode=0)
    packet = {'input_tokens':tokens, 'output_tokens':2, 'finish_reason':reason}
    process.communicate.return_value = (raw,
        ('ROKO_GENERATION '+json.dumps(packet)+'\n').encode()+CLEANUP)
    return process


class FreshProjectionTests(unittest.TestCase):
    def setUp(self):
        self.previous = conversation.session
        conversation.session = SimpleNamespace(context=[], cognitive_context=[])
        self.messages = [{'role':'system','content':'Talk briefly.'},
                         {'role':'user','content':'Hi'}]
        self.stderr = contextlib.redirect_stderr(io.StringIO())
        self.stderr.__enter__()

    def tearDown(self):
        conversation.session = self.previous
        self.stderr.__exit__(None,None,None)

    def history_messages(self):
        return [self.messages[0],
                {'role':'user','content':'Old fact.'},
                {'role':'assistant','content':'Old answer.'},
                {'role':'user','content':'Recent fact.'},
                {'role':'assistant','content':'Recent answer.'},self.messages[-1]]

    def test_default_path_does_not_count_or_publish_projection_metadata(self):
        value = provider('complete')
        with patch.object(fresh.subprocess,'Popen',return_value=generation()) as spawn:
            self.assertEqual(value.chat(self.messages),'Hello\n')
        self.assertEqual(spawn.call_count,1)
        self.assertNotIn('--count-tokens',spawn.call_args.args[0])
        self.assertIsNone(value.model_context)
        self.assertEqual(value.token_counter_receipts,[])
        self.assertNotIn('model_context',value.receipts[-1])

    def test_full_fit_keeps_exact_prompt_and_supervised_counter_receipt(self):
        value = provider()
        counted, generated = counter(), generation()
        with patch.object(fresh.subprocess,'Popen',side_effect=[counted,generated]) as spawn:
            self.assertEqual(value.chat(self.messages),'Hello\n')
        prompt = recovered.render(self.messages).encode()
        self.assertEqual(counted.communicate.call_args.args[0],prompt)
        self.assertEqual(generated.communicate.call_args.args[0],prompt)
        self.assertEqual(spawn.call_count,2)
        command = spawn.call_args_list[0].args[0]
        self.assertIn('--count-tokens',command)
        self.assertIn(f'/proc/{fresh.os.getpid()}/fd/0',command)
        self.assertIn('-B',command)
        self.assertLessEqual(float(command[command.index('--seconds')+1]),10)
        self.assertLessEqual(counted.communicate.call_args.kwargs['timeout'],10)
        self.assertTrue(spawn.call_args_list[0].kwargs['start_new_session'])
        metadata = value.model_context
        self.assertEqual(metadata['policy'],'extractive_v1')
        self.assertTrue(metadata['model_context_complete'])
        self.assertEqual(metadata['omitted_count'],0)
        self.assertEqual(metadata['token_count'],20)
        self.assertEqual(metadata['prompt_sha256'],hashlib.sha256(prompt).hexdigest())
        self.assertEqual(metadata['full_history_sha256'],hashlib.sha256(b'[]').hexdigest())
        receipt = value.token_counter_receipts[-1]
        raw = counted.communicate.return_value[0]
        self.assertEqual(base64.b64decode(receipt['stdout_base64']),raw)
        self.assertEqual(receipt['stdout_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(base64.b64decode(receipt['stderr_base64']),CLEANUP)
        self.assertEqual(receipt['input_tokens'],20)

    def test_over_budget_projects_without_modifying_full_history(self):
        value = provider()
        messages = self.history_messages()
        original = json.dumps(messages)
        first, compact, generated = counter(600), counter(20), generation()
        with patch.object(fresh.subprocess,'Popen',side_effect=[first,compact,generated]):
            self.assertEqual(value.chat(messages),'Hello\n')
        self.assertEqual(json.dumps(messages),original)
        self.assertNotEqual(first.communicate.call_args.args[0],compact.communicate.call_args.args[0])
        self.assertEqual(compact.communicate.call_args.args[0],generated.communicate.call_args.args[0])
        self.assertFalse(value.model_context['model_context_complete'])
        self.assertEqual(value.model_context['omitted_assistant_count'],1)
        self.assertEqual(value.model_context['excerpts'][0]['index'],0)
        self.assertFalse(value.model_context['authoritative_history_changed'])

    def test_full_renderer_byte_cap_can_project_before_exact_candidate_count(self):
        value = provider()
        history = []
        for _ in range(3):
            history.extend([{'role':'user','content':'old user ' * 350},
                            {'role':'assistant','content':'old reply ' * 350}])
        history.extend([{'role':'user','content':'Recent fact.'},
                        {'role':'assistant','content':'Recent answer.'}])
        messages = [self.messages[0]] + history + [self.messages[-1]]
        original = json.dumps(messages)
        with self.assertRaisesRegex(ValueError,'Prompt byte cap'):
            recovered.render(messages)
        counted, generated = counter(), generation()
        with patch.object(fresh.subprocess,'Popen',side_effect=[counted,generated]) as spawn:
            self.assertEqual(value.chat(messages),'Hello\n')
        self.assertEqual(spawn.call_count,2)
        candidate = counted.communicate.call_args.args[0]
        self.assertLessEqual(len(candidate),16384)
        self.assertEqual(candidate,generated.communicate.call_args.args[0])
        self.assertEqual(json.dumps(messages),original)
        self.assertIsNone(value.model_context['full_input_tokens'])
        self.assertEqual(value.model_context['full_count_unavailable_reason'],'renderer_byte_cap')
        self.assertEqual(value.model_context['token_count'],20)
        self.assertEqual(len(value.model_context['excerpts']),3)
        self.assertFalse(value.model_context['model_context_complete'])

    def test_other_full_renderer_errors_cannot_be_bypassed_by_projection(self):
        value = provider()
        bad = [{'role':'invalid','content':'Bad role'},self.messages[-1]]
        with patch.object(fresh.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'Invalid text message'):
                value.chat(bad)
        spawn.assert_not_called()
        self.assertIsNone(value.model_context)

    def test_projection_budget_failure_never_generates(self):
        value = provider()
        with patch.object(fresh.subprocess,'Popen',side_effect=lambda *a,**k:counter(600)) as spawn:
            with self.assertRaisesRegex(fresh.GenerationError,'context_projection_limit'):
                value.chat(self.history_messages())
        self.assertEqual(spawn.call_count,5)
        self.assertEqual(len(value.token_counter_receipts),5)
        self.assertEqual(value.receipts,[])
        self.assertIsNone(value.model_context)
        self.assertEqual(value.last_error,'context_projection_limit')

    def test_missing_capability_and_unknown_policy_fail_before_subprocess(self):
        for policy, capability in [('extractive_v1',None),('unknown','extractive_v1')]:
            with self.subTest(policy=policy):
                value = provider(policy)
                value.profile['context_projection'] = capability
                with patch.object(fresh.subprocess,'Popen') as spawn:
                    with self.assertRaisesRegex(fresh.GenerationError,'unsupported_context_policy'):
                        value.chat(self.messages)
                spawn.assert_not_called()
                self.assertIsNone(value.model_context)

    def test_invalid_counter_schema_retains_raw_evidence(self):
        bad = [b'{"input_tokens":true}',b'{"input_tokens":0}',b'{"input_tokens":-1}',
               b'{"input_tokens":1,"input_tokens":2}',b'{"input_tokens":1,"extra":0}',
               b'[]',b'not-json',b'\xff']
        for raw in bad:
            with self.subTest(raw=raw):
                value = provider()
                with patch.object(fresh.subprocess,'Popen',return_value=counter(raw=raw)) as spawn:
                    with self.assertRaisesRegex(fresh.GenerationError,'invalid_token_count_receipt'):
                        value.chat(self.messages)
                self.assertEqual(spawn.call_count,1)
                self.assertEqual(value.receipts,[])
                self.assertIsNone(value.model_context)
                receipt = value.token_counter_receipts[-1]
                self.assertEqual(base64.b64decode(receipt['stdout_base64']),raw)
                self.assertEqual(receipt['error'],'invalid_token_count_receipt')

    def test_failed_counter_or_missing_cleanup_does_not_generate(self):
        for process in [counter(returncode=1),counter(stderr=b'no cleanup')]:
            value = provider()
            with patch.object(fresh.subprocess,'Popen',return_value=process):
                with self.assertRaisesRegex(fresh.GenerationError,'context_projection_failed'):
                    value.chat(self.messages)
            self.assertIsNone(value.model_context)
            self.assertEqual(value.receipts,[])

    def test_timeout_terminates_and_retains_partial_counter_bytes(self):
        value = provider()
        process = counter()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired('fake',1,output=b'partial',stderr=b'waiting'),
            (b'partial',b'terminated')]
        with patch.object(fresh.subprocess,'Popen',return_value=process):
            with self.assertRaisesRegex(fresh.GenerationError,'context_projection_limit'):
                value.chat(self.messages)
        process.terminate.assert_called_once()
        receipt = value.token_counter_receipts[-1]
        self.assertEqual(receipt['cleanup'],'terminated_and_reaped')
        self.assertEqual(base64.b64decode(receipt['stdout_base64']),b'partial')
        self.assertEqual(receipt['error'],'context_projection_limit')
        self.assertIsNone(value.model_context)

    def test_timeout_escalates_to_owned_process_group_when_termination_stalls(self):
        value = provider()
        process = counter()
        process.communicate.side_effect = [subprocess.TimeoutExpired('fake',1),
            subprocess.TimeoutExpired('fake',.1,output=b'partial',stderr=b'still waiting')]
        with patch.object(fresh.subprocess,'Popen',return_value=process), patch.object(fresh.os,'killpg') as kill:
            with self.assertRaisesRegex(fresh.GenerationError,'context_projection_limit'):
                value.chat(self.messages)
        kill.assert_called_once_with(process.pid,signal.SIGKILL)
        process.wait.assert_called_once()
        self.assertLessEqual(process.wait.call_args.kwargs['timeout'],10)
        self.assertEqual(value.token_counter_receipts[-1]['cleanup'],'process_group_killed')

    def test_expired_planning_deadline_never_starts_counter(self):
        value = provider()
        with patch.object(fresh.time,'monotonic',return_value=100), patch.object(fresh.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(fresh.GenerationError,'context_projection_limit'):
                value._count_tokens('Hi',99)
        spawn.assert_not_called()

    def test_metadata_is_not_published_before_successful_decode_and_admission(self):
        for raw, reason, partial, error in [(b'\xff','eos',True,'invalid_output_encoding'),
                                           (b'Hello','length',False,'output_limit')]:
            with self.subTest(error=error):
                value = provider()
                value.model_context = {'stale':True}
                value.allow_partial = partial
                with patch.object(fresh.subprocess,'Popen',side_effect=[counter(),generation(raw=raw,reason=reason)]):
                    with self.assertRaisesRegex(fresh.GenerationError,error):
                        value.chat(self.messages)
                self.assertIsNone(value.model_context)
                self.assertNotIn('model_context',value.receipts[-1])

    def test_count_generation_mismatch_cannot_publish_projection(self):
        value = provider()
        with patch.object(fresh.subprocess,'Popen',side_effect=[counter(20),generation(21)]):
            with self.assertRaisesRegex(fresh.GenerationError,'context_projection_failed'):
                value.chat(self.messages)
        self.assertEqual(value.last_error,'context_projection_failed')
        self.assertIsNone(value.model_context)
        self.assertNotIn('model_context',value.receipts[-1])


if __name__ == '__main__': unittest.main()
