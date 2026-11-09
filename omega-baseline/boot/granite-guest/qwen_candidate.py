"""Explicit alternative Qwen GGUF candidate, never the default model."""
import json
from pathlib import Path
import time

import granite_guest as bounded

TOOLS_PREFIX = ('\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\n'
                'You are provided with function signatures within <tools></tools> XML tags:\n<tools>')
TOOLS_SUFFIX = ('\n</tools>\n\nFor each function call, return a json object with function name and '
                'arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n'
                '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call><|im_end|>\n')


def render_prompt(request):
    bounded.validate_request(request)
    first = request.messages[0]
    system = first.content if first.role == 'system' else 'You are Qwen, created by Alibaba Cloud. You are a helpful assistant.'
    prompt = '<|im_start|>system\n' + system + TOOLS_PREFIX
    prompt += ''.join('\n' + json.dumps(bounded.schema(tool), ensure_ascii=False) for tool in request.tools)
    prompt += TOOLS_SUFFIX
    for index, message in enumerate(request.messages):
        if index == 0 and message.role == 'system':
            continue
        prompt += '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>\n'
    prompt += '<|im_start|>assistant\n'
    if len(prompt.encode('utf-8')) > 16384:
        raise ValueError('Rendered prompt byte cap')
    return prompt


class QwenCandidateProvider(bounded.GraniteGuestProvider):
    """Same bounded native process and real Omega contract; Qwen template/assets."""
    def __init__(self, root, *, artifact='q4_k_m'):
        super().__init__(root, constrained=True)
        if artifact not in ('f16', 'q4_k_m'):
            raise ValueError('Unknown separately pinned Qwen candidate')
        self.artifact = artifact

    def start(self):
        self.ready = False
        deadline = time.monotonic() + 120
        lock = json.loads((self.root / 'build/qwen-guest-candidate-v1/artifacts.lock.json').read_text())
        if lock['status'] != 'converted-quantized-metadata-validated' or lock['default_model_changed']:
            raise ValueError('Candidate not admitted as a separate alternative')
        record = lock['artifacts'][self.artifact]
        self.model = self.root / record['path']
        if self.model.stat().st_size != record['bytes']:
            raise ValueError('Candidate model size mismatch')
        self.executable = self.root / lock['inference_helper']['path']
        bounded.verified_file(self.executable, lock['inference_helper']['sha256'], deadline)
        bounded.verified_file(self.model, record['sha256'], deadline)
        self.ready = True

    def _render_prompt(self, request):
        return render_prompt(request)

    def _parse_output(self, text, request):
        response = bounded.parse_tool(text, request)
        for call in response.calls:
            call.id = 'qwen-candidate-proposal-0'
        return response
