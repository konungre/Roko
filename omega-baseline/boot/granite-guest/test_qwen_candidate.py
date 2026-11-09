import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / 'vendor/PeTTa/repos/Omega/src')]
import providers
import granite_guest as bounded
import qwen_candidate
from test_source import request


class QwenTemplateTests(unittest.TestCase):
    def test_exact_pinned_template_subset(self):
        import jinja2.sandbox
        pin = next(m for m in json.loads((ROOT / 'models.lock.json').read_text()) if m['repo'].startswith('Qwen/'))
        config = json.loads((ROOT / pin['snapshot'] / 'tokenizer_config.json').read_text())
        env = jinja2.sandbox.ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        env.filters['tojson'] = lambda value: json.dumps(value, ensure_ascii=False)
        template = env.from_string(config['chat_template'])
        for sequence in ([('user', 'ready')], [('system', 'inert only'), ('user', '☃ " < > &')],
                         [('system', ''), ('user', 'one'), ('assistant', 'two'), ('system', 'three')]):
            for names in [('record_answer',), ('record_invoice',), tuple(bounded.ALLOWED)]:
                req = request([providers.llmRequestMessage(*pair) for pair in sequence], names)
                original = template.render(messages=[{'role': m.role, 'content': m.content} for m in req.messages],
                                           tools=[bounded.schema(t) for t in req.tools], add_generation_prompt=True)
                self.assertEqual(qwen_candidate.render_prompt(req), original)

    def test_candidate_tool_id_and_upstream_validation(self):
        provider = qwen_candidate.QwenCandidateProvider(ROOT)
        req = request()
        response = provider._parse_output('<tool_call>{"name":"record_answer","arguments":{"text":"data"}}</tool_call>', req)
        response = providers._validate_response(req, response)
        self.assertFalse(response.is_error())
        self.assertEqual(response.calls[0].id, 'qwen-candidate-proposal-0')
        self.assertIn('(record_answer "data")', providers.llmResponseToSExpr(response))

    def test_no_default_or_unknown_artifact_selection(self):
        with self.assertRaises(ValueError):
            qwen_candidate.QwenCandidateProvider(ROOT, artifact='automatic-default')


if __name__ == '__main__':
    unittest.main()
