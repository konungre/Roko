"""Explicit private rebuild candidate, separate from historical MORK admission.

The trusted host must review the runtime manifest and supply its digest out of
band. A self-written manifest is not authentication or a security approval.
Nothing here downloads, builds, auto-selects a runtime, or falls back to Python.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import native_mork


class RebuiltMORKCandidate:
    def __init__(self, manifest_path, *, expected_manifest_sha256, python_executable=None):
        self.manifest_path = Path(manifest_path)
        raw = self.manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
            raise native_mork.NativeMORKError('Rebuild manifest digest mismatch')
        self.manifest_sha256 = expected_manifest_sha256
        self.manifest = json.loads(raw)
        if self.manifest['schema'] != 'roko-private-mork-rebuild-v1':
            raise native_mork.NativeMORKError('Unsupported rebuild manifest')
        self.python_executable = str(Path(python_executable or sys.executable).resolve(strict=True))
        if python_executable is not None and self.python_executable not in self.manifest['files']:
            raise native_mork.NativeMORKError('Explicit Python is not in the rebuild manifest')
        self._verify()

    def _verify(self):
        for path, expected in self.manifest['files'].items():
            try:
                actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            except OSError as exc:
                raise native_mork.NativeMORKError('Rebuild closure file missing') from exc
            if actual != expected:
                raise native_mork.NativeMORKError('Rebuild closure file changed')
        for path in self.manifest['entrypoints'].values():
            if path not in self.manifest['files']:
                raise native_mork.NativeMORKError('Unpinned rebuild entrypoint')
        # Reuse only the existing authored supervisor/worker, with their original
        # hard-coded hashes. The manifest cannot substitute a different helper.
        for relative, expected in native_mork.CHILD_FILE_HASHES.items():
            if hashlib.sha256((native_mork.ROOT / relative).read_bytes()).hexdigest() != expected:
                raise native_mork.NativeMORKError('Native child helper hash mismatch')

    def query_facts(self, facts, query, *, timeout=3):
        facts, query = native_mork._validate(facts, query, timeout)
        request, decode = native_mork._encode(facts, query)
        self._verify()
        entry = self.manifest['entrypoints']
        with tempfile.TemporaryDirectory(prefix='rebuilt-mork-') as directory:
            env = {'PATH': '/usr/bin:/bin', 'HOME': directory, 'TMPDIR': directory,
                   'LANG': 'C', 'OMP_NUM_THREADS': '1',
                   'LD_LIBRARY_PATH': os.pathsep.join(self.manifest['library_directories'])}
            command = [self.python_executable, str(native_mork.ROOT/'scripts/no-network.py'),
                       self.python_executable, str(native_mork.ROOT/'integration/mork_child_limits.py'),
                       entry['ffi'], entry['swipl'],
                       str(native_mork.ROOT/'integration/mork_query_worker.pl'), entry['bridge']]
            payload = (request['atoms']+'\n'+request['query']+'\n').encode('ascii')
            output = native_mork._run(command, payload, cwd=directory, env=env, timeout=timeout)
        return {'implementation': 'native-mork-rebuild-bounded-facts',
                'runtime_manifest_sha256': self.manifest_sha256,
                'runtime_status': 'explicit-private-rebuild-candidate',
                'facts': native_mork._decode(output, facts, query, decode),
                'advisory_only': True, 'authorizes_actions': False,
                'persistent_state_changed': False, 'fresh_process': True,
                'network_denied': True}
