"""Admission-boundary tests only; fixture bytes are not a native runtime."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'source'))
import native_mork
from rebuilt_mork import RebuiltMORKCandidate


class RebuildBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = pathlib.Path(self.temp.name)/'fixture'
        self.file.write_bytes(b'not executable')
        self.manifest = pathlib.Path(self.temp.name)/'manifest.json'
        self.manifest.write_text(json.dumps({
            'schema': 'roko-private-mork-rebuild-v1',
            'files': {str(self.file): hashlib.sha256(self.file.read_bytes()).hexdigest()},
            'entrypoints': {k: str(self.file) for k in ('ffi','swipl','bridge')},
            'library_directories': []}))
        self.digest = hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def tearDown(self): self.temp.cleanup()

    def candidate(self):
        return RebuiltMORKCandidate(self.manifest, expected_manifest_sha256=self.digest)

    def test_manifest_must_match_host_digest(self):
        self.manifest.write_text('{}')
        with self.assertRaises(native_mork.NativeMORKError): self.candidate()

    def test_changed_runtime_fails_before_launch(self):
        candidate = self.candidate()
        self.file.write_bytes(b'changed')
        with patch('native_mork._run') as run:
            with self.assertRaises(native_mork.NativeMORKError):
                candidate.query_facts([], {'relation':'r','args':[None]})
            run.assert_not_called()

    def test_invalid_typed_input_never_executes_candidate(self):
        candidate = self.candidate()
        with patch('native_mork._run') as run:
            with self.assertRaises(ValueError):
                candidate.query_facts([], {'relation':'!(exec)','args':[None]})
            run.assert_not_called()
