#!/usr/bin/env python3
"""Explicitly authorized isolated conversion; original weights remain unchanged."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'build-src/qwen-converter-stage'
OUT = ROOT / 'build/qwen-guest-candidate-v1'
LLAMA = ROOT / 'build-src/llama.cpp'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    if sys.argv[1:] != ['--convert-after-lane-grant'] or Path(sys.prefix) != STAGE / 'venv':
        raise ValueError('Explicit lane grant flag and isolated interpreter required')
    if OUT.exists():
        raise ValueError('Never overwrite a conversion attempt')
    if subprocess.check_output(['git', '-C', str(LLAMA), 'rev-parse', 'HEAD'], text=True).strip() != 'f7591a6a01f9273de03331732bdc0b39721168be':
        raise ValueError('Wrong llama source commit')
    if subprocess.check_output(['git', '-C', str(LLAMA), 'status', '--porcelain', '--untracked-files=no'], text=True):
        raise ValueError('Pinned llama sources changed')
    preflight = json.loads((STAGE / 'compatibility-preflight.json').read_text())
    for name, expected in preflight['packages'].items():
        distribution = importlib.metadata.distribution(name)
        if (distribution.version != expected['version']
                or hashlib.sha256(distribution.read_text('METADATA').encode()).hexdigest() != expected['metadata_sha256']
                or hashlib.sha256(distribution.read_text('RECORD').encode()).hexdigest() != expected['record_sha256']):
            raise ValueError('Converter dependency metadata changed: ' + name)
    pin = next(m for m in json.loads((ROOT / 'models.lock.json').read_text())
               if m['repo'] == 'Qwen/Qwen2.5-0.5B-Instruct')
    snapshot = ROOT / pin['snapshot']
    for name, digest in pin['files'].items():
        if sha(snapshot / name) != digest:
            raise ValueError('Source model pin mismatch: ' + name)
    OUT.mkdir(mode=0o700)
    (OUT / 'tmp').mkdir(mode=0o700)
    output = OUT / 'qwen2.5-0.5b-instruct-f16.gguf'
    command = [sys.executable, str(LLAMA / 'convert_hf_to_gguf.py'), str(snapshot),
               '--outfile', str(output), '--outtype', 'f16', '--use-temp-file']
    report = {'status': 'converting', 'explicit_alternative_not_default': True,
              'source': pin, 'complete_source_hashes_verified': True,
              'llama_commit': 'f7591a6a01f9273de03331732bdc0b39721168be',
              'converter_sha256': sha(LLAMA / 'convert_hf_to_gguf.py'),
              'dependencies': preflight['packages'], 'upstream_requirements_match': False,
              'command': command, 'original_model_modified': False,
              'prior_accuracy_failure': 'results/native-provider.json: 2+2 returned 3 and was rejected'}
    (OUT / 'conversion.json').write_text(json.dumps(report, indent=2) + '\n')
    env = dict(os.environ, TMPDIR=str(OUT / 'tmp'), HF_HUB_OFFLINE='1',
               TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    result = subprocess.run(command, env=env, check=False)
    report['returncode'] = result.returncode
    report['status'] = 'converted' if result.returncode == 0 else 'conversion-failed'
    if result.returncode == 0:
        report['output'] = {'path': str(output.relative_to(ROOT)), 'bytes': output.stat().st_size, 'sha256': sha(output)}
    (OUT / 'conversion.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
