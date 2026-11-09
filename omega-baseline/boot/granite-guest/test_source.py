"""No weights, native inference, compilation or VM launch in these tests."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OMEGA = ROOT / 'vendor/PeTTa/repos/Omega'
sys.path[:0] = [str(HERE), str(OMEGA / 'src')]
import providers
import granite_guest as guest
import prepare


def request(messages=None, names=('record_answer',), cap=64):
    tools = []
    for name in names:
        tool = providers.LLMTool().with_name(name).with_description('Inert test data, not an action.')
        for param in guest.ALLOWED[name]:
            tool.add_parameter(providers.LLMToolParameter().with_name(param))
        tools.append(tool)
    return providers.LLMRequest().with_messages(messages or [providers.llmRequestMessage('user', 'Repeat ready')]).with_tools(tools).with_max_tokens(cap)


class ProviderTests(unittest.TestCase):
    def test_real_upstream_registry_and_serializer(self):
        class InertFixture(guest.GraniteGuestProvider):
            def start(self):
                self.ready = True

            def chat(self, req):
                return guest.parse_tool('<tool_call>{"name":"record_answer","arguments":{"text":"ready"}}</tool_call>', req)

        fixture = InertFixture(ROOT)
        providers.registerLLMProvider('guest-unit-only', fixture)
        providers.llmProviderStart('guest-unit-only')
        req = request()
        response = providers.llmProviderChat(req)
        self.assertFalse(response.is_error())
        self.assertIs(response.calls[0].tool, req.tools[0])
        self.assertEqual(providers.llmResponseToSExpr(response), '((granite-guest-proposal-0 (record_answer "ready")))')

    def test_upstream_schema_parity(self):
        tree = ast.parse((OMEGA / 'providers/lib_llm_ext.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AIProvider')
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'convert_tool')
        scope = {'LLMTool': providers.LLMTool, 'Dict': dict}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'unchanged_upstream_convert_tool', 'exec'), scope)
        for tool in request(names=tuple(guest.ALLOWED)).tools:
            self.assertEqual(guest.schema(tool), scope['convert_tool'](None, tool))

    def test_pinned_template_subset_parity(self):
        import jinja2.sandbox
        lock = json.loads((ROOT / 'granite-model.lock.json').read_text())
        template = ROOT / lock['tokenizer_path'] / 'chat_template.jinja'
        self.assertEqual(prepare.sha(template.read_bytes()), lock['tokenizer_files']['chat_template.jinja'])
        env = jinja2.sandbox.ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        env.filters['tojson'] = lambda value: json.dumps(value, ensure_ascii=False)
        original = env.from_string(template.read_text())
        sequences = [
            [('user', 'repeat ready')],
            [('system', 'Use exactly one recording tool.'), ('user', 'Snowman ☃ and quotes " < > &')],
            [('system', ''), ('user', 'one'), ('assistant', 'two'), ('system', 'three')],
        ]
        for names in [('record_answer',), ('record_invoice',), tuple(guest.ALLOWED)]:
            for sequence in sequences:
                req = request([providers.llmRequestMessage(*m) for m in sequence], names)
                expected = original.render(messages=[{'role': m.role, 'content': m.content} for m in req.messages],
                                           tools=[guest.schema(t) for t in req.tools], add_generation_prompt=True)
                self.assertEqual(guest.render_prompt(req), expected)

    def test_invalid_request_caps_and_types(self):
        for cap in (0, 65, True, '64'):
            with self.assertRaises(ValueError):
                guest.render_prompt(request(cap=cap))
        for message in (providers.llmRequestMessage('tool', 'x'),
                        providers.llmRequestMessage('user', 'x' * 2049),
                        providers.LLMToolCallMessage().with_role('assistant').with_content('x')):
            with self.assertRaises(ValueError):
                guest.render_prompt(request([message]))

    def test_unapproved_and_duplicate_tool(self):
        req = request()
        req.tools[0].name = 'shell'
        with self.assertRaises(ValueError):
            guest.validate_request(req)
        req = request()
        req.tools.append(req.tools[0])
        with self.assertRaises(ValueError):
            guest.validate_request(req)

    def test_malformed_proposals_fail_closed(self):
        valid = '<tool_call>{"name":"record_answer","arguments":{"text":"ready"}}</tool_call>'
        for text in ('ready', valid + valid, 'prefix ' + valid,
                     valid.replace('record_answer', 'shell'),
                     valid.replace('"text":"ready"', '"text":"ready","text":"bad"'),
                     valid.replace('"text":"ready"', '"text":"ready","command":"sh"'),
                     valid.replace('"text":"ready"', '"text":1')):
            with self.assertRaises(ValueError):
                guest.parse_tool(text, request())

    def test_grammar_is_schema_not_answer(self):
        grammar = guest.tool_grammar(['record_answer'])
        self.assertIn('char*', grammar)
        self.assertNotIn('ready', grammar)
        self.assertNotIn('record_invoice', grammar)

    def test_not_started_fails_closed(self):
        response = guest.GraniteGuestProvider(ROOT).chat(request())
        self.assertTrue(response.is_error())
        self.assertFalse(response.calls)


class SourceTests(unittest.TestCase):
    def test_pins_and_source_only_overlay(self):
        files, manifest = prepare.sources()
        self.assertLess(manifest['source_bytes'], 512 * 1024)
        self.assertFalse(manifest['validation']['guest_inference_executed'])
        self.assertFalse(manifest['model_disk']['formatted'])
        self.assertFalse(any(p.endswith(('.gguf', '.so')) for p in files))
        self.assertIn(b'GraniteGuestProvider as GranitePipeProvider', files['opt/roko/scripts/roko.py'])
        self.assertIn(b"],64,'none',[tool])", files['opt/roko/scripts/roko.py'])
        self.assertEqual(files['opt/roko/vendor/PeTTa/repos/Omega/src/providers.py'], (OMEGA / 'src/providers.py').read_bytes())

    def test_dependency_closure_without_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / 'overlay'
            prepare.stage(overlay)
            base = overlay / 'opt/roko'
            program = """
import sys
sys.path[:0] = [sys.argv[1] + '/vendor/guest-python', sys.argv[1] + '/vendor/PeTTa/repos/Omega/src', sys.argv[1] + '/adapters']
import yaml, config, providers, granite_guest
assert yaml.__with_libyaml__ is False
assert yaml.safe_load('limit: 64')['limit'] == 64
assert isinstance(granite_guest.GraniteGuestProvider(sys.argv[1]), providers.LLMProvider)
print('SOURCE_CLOSURE_PASSED', sys.version_info[:2])
"""
            result = subprocess.run([sys.executable, '-S', '-B', '-c', program, str(base)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('SOURCE_CLOSURE_PASSED', result.stdout)

    def test_source_overlay_never_claims_built(self):
        files, _ = prepare.sources()
        runtime = json.loads(files['opt/roko/granite-guest-runtime.lock.json'])
        self.assertEqual(runtime['status'], 'source-only-not-built')
        self.assertNotIn('runtime/granite/omega-granite-guest', runtime['files'])


if __name__ == '__main__':
    unittest.main()
