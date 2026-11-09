#!/usr/bin/env python3
"""Pin both GGUF artifacts and validate metadata without evaluating a model."""
import collections
import gc
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/qwen-guest-candidate-v1'
sys.path.insert(0, str(ROOT / 'build-src/llama.cpp/gguf-py'))
import gguf


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    if (OUT / 'artifacts.lock.json').exists():
        raise ValueError('Never overwrite artifact admission')
    conversion = json.loads((OUT / 'conversion.json').read_text())
    quantization = json.loads((ROOT / 'results/qwen-guest-candidate/quantization/monitor.json').read_text())
    if conversion['status'] != 'converted' or quantization['returncode'] or quantization['termination_reason']:
        raise ValueError('Conversion/quantization did not complete cleanly')
    tokenizer = json.loads((ROOT / conversion['source']['snapshot'] / 'tokenizer_config.json').read_text())
    artifacts = {}
    shapes = None
    for key, filename, file_type in [('f16', 'qwen2.5-0.5b-instruct-f16.gguf', 1),
                                     ('q4_k_m', 'qwen2.5-0.5b-instruct-Q4_K_M.gguf', 15)]:
        path = OUT / filename
        reader = gguf.GGUFReader(path, mode='r')
        expected = {'general.architecture': 'qwen2', 'general.file_type': file_type,
                    'qwen2.block_count': 24, 'qwen2.embedding_length': 896,
                    'qwen2.attention.head_count': 14, 'qwen2.attention.head_count_kv': 2,
                    'qwen2.context_length': 32768, 'tokenizer.ggml.pre': 'qwen2',
                    'tokenizer.ggml.bos_token_id': 151643, 'tokenizer.ggml.eos_token_id': 151645}
        values = {name: reader.fields[name].contents() for name in expected}
        if values != expected:
            raise ValueError('Unexpected model metadata: ' + repr(values))
        template = reader.fields['tokenizer.chat_template'].contents()
        if template != tokenizer['chat_template']:
            raise ValueError('Converted chat template differs from original')
        token_count = len(reader.fields['tokenizer.ggml.tokens'].data)
        inventory = {t.name: list(map(int, t.shape)) for t in reader.tensors}
        parameters = sum(int(t.n_elements) for t in reader.tensors)
        if len(inventory) != 290 or parameters != 494032768 or token_count != 151936:
            raise ValueError('Tensor or vocabulary count changed')
        if shapes is not None and inventory != shapes:
            raise ValueError('Quantization changed tensor names or dimensions')
        shapes = inventory
        types = dict(collections.Counter(t.tensor_type.name for t in reader.tensors))
        del reader
        gc.collect()
        artifacts[key] = {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
                          'sha256': sha(path), 'metadata': values, 'tensor_count': len(inventory),
                          'stored_parameters': parameters, 'vocabulary_entries': token_count,
                          'tensor_types': types, 'chat_template_sha256': hashlib.sha256(template.encode()).hexdigest()}
    if artifacts['f16']['sha256'] != conversion['output']['sha256']:
        raise ValueError('Converted F16 changed before quantization')
    helper = json.loads((ROOT / 'results/granite-guest-build/binary-admission.json').read_text())
    if sha(ROOT / helper['binary']) != helper['binary_sha256']:
        raise ValueError('Portable helper changed')
    host = json.loads((ROOT / 'granite-runtime.lock.json').read_text())
    libraries = {name: digest for name, digest in host['files'].items() if name.startswith('build/llama/bin/')}
    for name, digest in libraries.items():
        if sha(ROOT / name) != digest:
            raise ValueError('Pinned shared host library changed')
    result = {'status': 'converted-quantized-metadata-validated', 'default_model_changed': False,
              'candidate_model': conversion['source'], 'artifacts': artifacts,
              'llama_commit': conversion['llama_commit'], 'converter_sha256': conversion['converter_sha256'],
              'converter_dependencies': conversion['dependencies'], 'upstream_requirements_match': False,
              'quantizer': {'path': 'build/qwen-quantizer/bin/llama-quantize',
                            'sha256': sha(ROOT / 'build/qwen-quantizer/bin/llama-quantize'),
                            'source_sha256': {name: sha(ROOT / name) for name in (
                                'build-src/llama.cpp/tools/quantize/quantize.cpp',
                                'build-src/llama.cpp/tools/quantize/main.cpp',
                                'build-src/llama.cpp/tools/quantize/CMakeLists.txt')},
                            'host_only_shared_libraries': libraries, 'threads': 1},
              'inference_helper': {'path': helper['binary'], 'sha256': helper['binary_sha256'],
                                   'generic_x86_64': True, 'repack': False},
              'original_weights_modified': False, 'source_revision_preserved': True,
              'conversion_resource_report': 'results/qwen-guest-candidate/conversion/monitor.json',
              'quantization_resource_report': 'results/qwen-guest-candidate/quantization/monitor.json',
              'guest_tested': False, 'prior_accuracy_failure': conversion['prior_accuracy_failure']}
    (OUT / 'artifacts.lock.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
