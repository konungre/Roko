#!/usr/bin/env python3
"""Import/tokenizer/tiny-tensor checks only. Never read model tensor payloads."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'build-src/qwen-converter-stage'
LLAMA = ROOT / 'build-src/llama.cpp'


def main():
    if Path(sys.prefix) != STAGE / 'venv':
        raise ValueError('Use the isolated converter interpreter')
    if any(os.environ.get(name) != '1' for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')):
        raise ValueError('Offline environment required')
    try:
        stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError:
        pass
    else:
        stream.close()
        raise ValueError('Network-denying wrapper required')
    pin = next(m for m in json.loads((ROOT / 'models.lock.json').read_text())
               if m['repo'] == 'Qwen/Qwen2.5-0.5B-Instruct')
    snapshot = ROOT / pin['snapshot']
    checked = {}
    for name, digest in pin['files'].items():
        if name == 'model.safetensors':
            continue
        actual = hashlib.sha256((snapshot / name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError('Local tokenizer/configuration pin mismatch: ' + name)
        checked[name] = actual
    sys.path[:0] = [str(LLAMA), str(LLAMA / 'gguf-py')]
    import numpy
    import sentencepiece
    import torch
    import transformers
    import conversion
    from conversion.base import LazyTorchTensor

    torch.set_num_threads(1)
    # Import the official CLI without entering its main conversion function.
    runpy.run_path(str(LLAMA / 'convert_hf_to_gguf.py'), run_name='converter_import_preflight')
    model_class = conversion.get_model_class('Qwen2ForCausalLM')
    if model_class.__name__ != 'Qwen2Model':
        raise ValueError('Unexpected official converter model class')
    config = transformers.AutoConfig.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    tokenizer = transformers.AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    if config.model_type != 'qwen2' or max(tokenizer.vocab.values()) >= config.vocab_size:
        raise ValueError('Tokenizer/configuration API mismatch')
    # Uninitialized converter object: only metadata methods; no constructor or weights.
    probe = object.__new__(model_class)
    probe.dir_model = snapshot
    try:
        probe._create_vocab_sentencepiece()
    except FileNotFoundError:
        sentencepiece_to_bpe_fallback = True
    else:
        raise ValueError('Expected pinned Qwen BPE input, not tokenizer.model')
    pretokenizer = probe.get_vocab_base_pre(tokenizer)
    if pretokenizer != 'qwen2':
        raise ValueError('Pinned converter did not recognize Qwen pretokenizer')
    tools = [{'type': 'function', 'function': {'name': 'record_answer', 'description': 'Inert data only',
              'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}},
                             'required': ['text'], 'additionalProperties': False}}}]
    prompt = tokenizer.apply_chat_template([{'role': 'user', 'content': 'Repeat ready.'}],
                                          tools=tools, tokenize=False, add_generation_prompt=True)
    if '<|im_start|>assistant\n' not in prompt or '<tool_call>' not in prompt:
        raise ValueError('Pinned tool template did not render')
    # Four synthetic values exercise the converter's lazy BF16->F16/NumPy path.
    tiny = torch.tensor([0, 1, -2, 3.5], dtype=torch.bfloat16)
    lazy = LazyTorchTensor.from_eager(tiny)
    values = LazyTorchTensor.to_eager(lazy.to(torch.float16)).numpy()
    if values.dtype != numpy.float16 or values.tolist() != [0, 1, -2, 3.5]:
        raise ValueError('Tiny tensor API compatibility failed')
    package_names = ('sentencepiece', 'torch', 'transformers', 'numpy', 'protobuf', 'safetensors', 'tokenizers')
    packages = {}
    for name in package_names:
        distribution = importlib.metadata.distribution(name)
        packages[name] = {'version': distribution.version,
                          'metadata_sha256': hashlib.sha256(distribution.read_text('METADATA').encode()).hexdigest(),
                          'record_sha256': hashlib.sha256(distribution.read_text('RECORD').encode()).hexdigest()}
    report = {'status': 'import-tokenizer-tiny-tensor-preflight-passed',
              'interpreter': sys.executable, 'prefix': sys.prefix,
              'upstream_requirements_match': False,
              'compatibility_scope': 'CLI import, Qwen class registration, local config/tokenizer APIs, recognized pretokenizer, tool template rendering and four-value lazy dtype conversion only',
              'full_conversion_compatibility_proven': False, 'model_tensor_payload_read': False,
              'model_conversion_executed': False, 'quantization_executed': False, 'model_inference_executed': False,
              'network_denied': True, 'shared_dependency_root': str(ROOT / '.venv/lib/python3.12/site-packages'),
              'sentencepiece_path': sentencepiece.__file__, 'torch_path': torch.__file__,
              'transformers_path': transformers.__file__, 'packages': packages,
              'verified_nonweight_model_sources': checked,
              'sentencepiece_to_bpe_fallback': sentencepiece_to_bpe_fallback,
              'recognized_pretokenizer': pretokenizer, 'tokenizer_class': type(tokenizer).__name__,
              'example_rendered_prompt_tokens': len(tokenizer.encode(prompt, add_special_tokens=False)),
              'converter_sha256': hashlib.sha256((LLAMA / 'convert_hf_to_gguf.py').read_bytes()).hexdigest()}
    destination = STAGE / 'compatibility-preflight.json'
    if destination.exists():
        raise ValueError('Do not overwrite compatibility evidence')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
