"""Pure source/controller tests with explicit doubles, never native evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / 'adapters'),
    str(ROOT / 'recovery/guest-cognition/model-provider-candidate-001/adapters'),
    str(ROOT / 'recovery/guest-cognition/model-provider-candidate-002/adapters'),
    str(ROOT / 'boot/artifacts/recipes-0.21/granite-fourcore-tested/vendor/PeTTa/repos/Omega/src'),
    str(ROOT / 'boot/artifacts/recipes-0.21/granite-fourcore-tested/vendor/guest-python')]
import live_contract as contract
import live_controller as controller
import providers
import granite_guest
from state_store import StateStore


class BlockDouble:
    def __init__(self):
        self.fd = 91  # Never an OS descriptor; no OS operations receive it.
        self.report = {'test_double_only': True, 'prefix_sha256': 'a' * 64}
    def close(self):
        self.fd = None


class ProviderDouble(providers.LLMProvider):
    def __init__(self, proposal):
        self.proposal = proposal
        self.ready = False
        self._raw_model = None
        self.backend = 'pure-test-double'
        self.last = {}
        self.stdout_bytes = self.stderr_bytes = b''
        self.calls = 0
        self.on_start = self.on_chat = self.on_stop = lambda: None
        self.marker = controller.NATIVE_COMPLETE
        self.wire_override = None
    def start(self):
        self.ready = True
        self._raw_model = BlockDouble()
        self.on_start()
    def chat(self, req):
        self.calls += 1
        self.stdout_bytes = self.wire_override if self.wire_override is not None else ('<tool_call>' + json.dumps(self.proposal) + '</tool_call>').encode()
        self.stderr_bytes = self.marker + b'\n'
        self.last = {'returncode': 0, 'executed_actions': 0}
        self.on_chat()
        return granite_guest.parse_tool(self.stdout_bytes.decode(), req)
    def stop(self):
        self.on_stop()
        self.ready = False
        if self._raw_model is not None:
            self._raw_model.close()
            self._raw_model = None


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'state').mkdir()
        (self.directory / 'out').mkdir()
        self.store = StateStore(self.directory / 'state')
        self.task_id = 'live-' + '1' * 32
        self.request = {'version': 1, 'kind': 'arithmetic', 'goal': 'Compute exactly this.', 'evidence': 'Arithmetic: 13 * 17.'}
        self.provider = ProviderDouble({'name': 'record_answer', 'arguments': {'text': '221'}})
        self.patches = [patch('subprocess.Popen', side_effect=AssertionError('Native execution forbidden in pure tests')),
                        patch('subprocess.run', side_effect=AssertionError('Native execution forbidden in pure tests'))]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        old = dict(providers._llmProviderRegistry)
        current = providers._llmprovider
        def reset():
            providers._llmProviderRegistry.clear()
            providers._llmProviderRegistry.update(old)
            providers._llmprovider = current
        self.addCleanup(reset)
    def run_request(self, recheck=None):
        return controller._run(self.request, self.task_id, self.store, self.directory / 'out',
            provider=self.provider, registry=providers, renderer=granite_guest,
            recheck=recheck or (lambda block, deadline: dict(block.report)))
    def test_fresh_actual_controller_checks_changed_arithmetic(self):
        report = self.run_request()
        self.assertTrue(report['accepted'])
        self.assertEqual(report['final_revision'], 5)
        self.assertEqual(report['snapshot']['phase'], 'verified')
        self.assertEqual(report['snapshot']['evidence']['source']['text'], 'Arithmetic: 13 * 17.')
        self.assertEqual(self.provider.calls, 1)
        self.assertTrue(report['model_descriptor_closed'])
        self.assertFalse(report['ecan_exercised'])
        self.assertFalse(report['metta_roundtrip_exercised'])
        self.assertEqual(report['executed_actions'], 0)
    def test_incorrect_model_answer_is_saved_and_rejected_not_repaired(self):
        self.provider.proposal['arguments']['text'] = '56'
        result = self.run_request()
        self.assertFalse(result['accepted'])
        self.assertIsNone(result['error'])
        self.assertEqual(result['proposal']['arguments']['text'], '56')
        self.assertEqual(result['final_revision'], 5)
        self.assertEqual(result['snapshot']['phase'], 'open')
    def test_literal_quote_including_code_like_text(self):
        text = '$(touch /tmp/not-executed) Ω "literal"'
        self.request.update(kind='quote', evidence=text)
        self.provider.proposal['arguments']['text'] = text
        result = self.run_request()
        self.assertTrue(result['accepted'])
        prompt = (self.directory / 'out/prompt.txt').read_text()
        self.assertIn('$(touch /tmp/not-executed)', prompt)
        self.assertEqual(result['checked']['checker'], 'exact-quote-v1')
    def test_invoice_uses_real_independent_checker(self):
        self.request.update(kind='invoice', evidence='Invoice AB92; total 142.39.')
        self.provider.proposal = {'name': 'record_invoice', 'arguments': {'invoice': 'AB92', 'total': '142.39'}}
        result = self.run_request()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['checked']['checker'], 'strict-invoice-v1')
    def test_negative_arithmetic(self):
        self.request['evidence'] = 'Arithmetic: -12 - 7.'
        self.provider.proposal['arguments']['text'] = '-19'
        self.assertTrue(self.run_request()['accepted'])
    def test_prompt_does_not_contain_computed_answer(self):
        self.run_request()
        prompt = (self.directory / 'out/prompt.txt').read_text()
        self.assertIn('Arithmetic: 13 * 17.', prompt)
        self.assertNotIn('221', prompt)
        self.assertNotIn('Arithmetic: 7 * 8.', prompt)
    def test_malformed_model_output_preserved(self):
        self.provider.wire_override = b'not a proposal'
        result = self.run_request()
        self.assertFalse(result['accepted'])
        self.assertIsNotNone(result['error'])
        self.assertEqual((self.directory / 'out/model.stdout').read_bytes(), b'not a proposal')
        self.assertEqual(self.store.load(self.task_id)[1], 3)
    def test_missing_native_cleanup_marker_fails_closed(self):
        self.provider.marker = b'no proof'
        result = self.run_request()
        self.assertFalse(result['accepted'])
        self.assertIn('cleanup evidence', result['error'])
        self.assertEqual(self.store.load(self.task_id)[1], 3)
    def test_posthash_failure_no_proposal_commit(self):
        result = self.run_request(recheck=lambda block, deadline: {'wrong': True})
        self.assertFalse(result['accepted'])
        self.assertFalse(result['model_hash_unchanged'])
        self.assertTrue(result['model_descriptor_closed'])
        self.assertEqual(self.store.load(self.task_id)[1], 3)
    def test_competing_write_never_rebases(self):
        def mutate():
            state, revision = self.store.load(self.task_id)
            state.goal = 'Changed while model was working'
            self.store.save(state, expected_revision=revision)
        self.provider.on_chat = mutate
        result = self.run_request()
        self.assertTrue(result['state_stale'])
        self.assertFalse(result['accepted'])
        self.assertIsNone(self.store.load(self.task_id)[0].snapshot()['proposal'])
    def test_startup_failure_stops_without_inference(self):
        def fail():
            raise ValueError('test startup failure')
        self.provider.on_start = fail
        result = self.run_request()
        self.assertEqual(self.provider.calls, 0)
        self.assertTrue(result['model_descriptor_closed'])
        self.assertFalse(result['accepted'])
    def test_cancellation_skips_expensive_hash_and_closes(self):
        def cancel():
            raise controller.Cancelled('test cancellation')
        self.provider.on_chat = cancel
        def forbidden(*args):
            self.fail('No expensive model posthash after cancellation')
        result = self.run_request(recheck=forbidden)
        self.assertIn('Cancelled', result['error'])
        self.assertTrue(result['model_descriptor_closed'])
        self.assertFalse(result['accepted'])
        self.assertEqual(self.store.load(self.task_id)[1], 3)
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            contract.decode_request(b'{"version":1,"version":1,"kind":"quote","goal":"g","evidence":"e"}')
    def test_unexpected_fields_and_grammars_rejected(self):
        for update in ({'kind': 'shell'}, {'version': True}, {'goal': 'x' * 513}, {'evidence': '7*8'}, {'evidence': 'Arithmetic: 1 / 2.'}, {'command': 'echo bad'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                contract.validate_request({**self.request, **update})
    def test_fresh_ids_not_provided_by_request(self):
        with self.assertRaises(ValueError):
            contract.validate_request({**self.request, 'task_id': 'reuse'})
        with self.assertRaises(ValueError):
            contract.create_state(self.store, '../../bad', self.request)
    def test_reopen_state_recomputes_checker(self):
        result = self.run_request()
        loaded, revision = StateStore(self.directory / 'state').load(self.task_id)
        self.assertEqual(loaded.snapshot(), result['snapshot'])
        self.assertEqual(revision, 5)
    def test_unsafe_symlink_state_ancestry_rejected(self):
        target = self.directory / 'target'
        target.mkdir()
        link = self.directory / 'link'
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            controller.private_directory(link)

if __name__ == '__main__':
    unittest.main()
