"""Qualification tests use a synthetic file closure, never claim native queries."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qualify_fresh
from mork_host import native_mork


class MORKQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root/'synthetic-runtime'
        self.runtime.write_bytes(b'qualification test fixture, not executable')
        python = str(Path(sys.executable).resolve())
        self.profile = {'python':python,'files':{}}
        self.manifest = self.root/'manifest.json'
        self.data = {'schema':'roko-private-mork-rebuild-v1',
            'files':{python:qualify_fresh.sha(python),
                     str(self.runtime):qualify_fresh.sha(self.runtime)},
            'entrypoints':dict.fromkeys(('ffi','bridge','swipl'),str(self.runtime)),
            'library_directories':[]}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data))
        self.digest = qualify_fresh.sha(self.manifest)

    def test_pins_full_closure_and_authored_helpers(self):
        qualify_fresh.add_mork_profile(self.profile,self.manifest,self.digest)
        self.assertEqual(self.profile['mork_memory'],
            {'manifest':str(self.manifest),'manifest_sha256':self.digest})
        for path,digest in self.data['files'].items():
            self.assertEqual(self.profile['files'][path],digest)
        expected = {'native_mork.py','rebuilt_mork.py','mork_host.py',
            'mork_supervise.py','mork_v2.py','fresh_supervise.py',
            'no-network.py','mork_child_limits.py','mork_query_worker.pl','manifest.json'}
        self.assertTrue(expected <= {Path(p).name for p in self.profile['files']})

    def test_optional_pair_and_missing_option(self):
        original = copy.deepcopy(self.profile)
        qualify_fresh.add_mork_profile(self.profile,None,None)
        self.assertEqual(self.profile,original)
        for path,digest in [(None,self.digest),(self.manifest,None)]:
            with self.assertRaisesRegex(ValueError,'Both MORK'):
                qualify_fresh.add_mork_profile(self.profile,path,digest)

    def test_tampered_manifest_or_closure_fails(self):
        with self.assertRaisesRegex(native_mork.NativeMORKError,'digest mismatch'):
            qualify_fresh.add_mork_profile(self.profile,self.manifest,'0'*64)
        self.runtime.write_bytes(b'changed')
        with self.assertRaisesRegex(native_mork.NativeMORKError,'file changed'):
            qualify_fresh.add_mork_profile(self.profile,self.manifest,self.digest)
        self.assertNotIn('mork_memory',self.profile)

    def test_unpinned_python_and_entrypoint_fail(self):
        del self.data['files'][self.profile['python']]
        self.write_manifest()
        with self.assertRaisesRegex(native_mork.NativeMORKError,'Python'):
            qualify_fresh.add_mork_profile(self.profile,self.manifest,self.digest)
        self.data['files'][self.profile['python']] = qualify_fresh.sha(self.profile['python'])
        self.data['entrypoints']['ffi'] = str(self.root/'unpinned')
        self.write_manifest()
        with self.assertRaisesRegex(native_mork.NativeMORKError,'Unpinned'):
            qualify_fresh.add_mork_profile(self.profile,self.manifest,self.digest)

    def test_conflicting_profile_pin_preserved(self):
        self.profile['files'][str(self.runtime)] = '0'*64
        original = copy.deepcopy(self.profile)
        with self.assertRaisesRegex(ValueError,'Conflicting MORK source'):
            qualify_fresh.add_mork_profile(self.profile,self.manifest,self.digest)
        self.assertEqual(self.profile,original)


if __name__ == '__main__':
    unittest.main()
