"""Synthetic rejection tests; actual native proof comes from explicit qualification."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
spec=importlib.util.spec_from_file_location('airis_host_qualification',Path(__file__).with_name('qualify.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
from contract import expected,response

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.request=q.fixture('increment',1,7)
        native=dict(predictions=expected(self.request),learned_rules=2,rule_updates=2,steps=4,
            knowledge_snapshot_sha256='0'*64,max_graph_nodes=4,max_knowledge_keys=4,
            upstream_line_events=100,planner_calls=0)
        self.packet=dict(version=1,request=self.request,native=native,response=response(self.request,native),
            network_denial_observed=True,upstream_sha256='synthetic',runtime=dict(
                executable_mappings=['/test/map'],imported_files={'/test/source':'test'},
                flags=dict(isolated=1,no_site=1,no_user_site=1,dont_write_bytecode=1),
                prefix='/test',base_prefix='/test',search_path=[str(q.ROOT/'source'),
                    '/test/lib/python312.zip','/test/lib/python3.12','/test/lib/python3.12/lib-dynload']))
        self.manifest=dict(python='/test/bin/python',files={'/test/map':'map','/test/source':'test',
            str(q.ROOT/'upstream/airis.py'):'synthetic'})

    def test_consistent_synthetic_packet(self):
        self.assertEqual(q.check(self.packet,self.request,self.manifest)['predictions'],expected(self.request))

    def test_false_learning_or_authority_rejected(self):
        for field,value in [('network_denial_observed',False),('upstream_sha256','changed'),('response',{})]:
            with self.subTest(field=field):
                packet=copy.deepcopy(self.packet);packet[field]=value
                with self.assertRaises(ValueError):q.check(packet,self.request,self.manifest)
        for field,value in [('learned_rules',1),('rule_updates',0),('planner_calls',1),('predictions',{})]:
            with self.subTest(native=field):
                packet=copy.deepcopy(self.packet);packet['native'][field]=value
                with self.assertRaises(ValueError):q.check(packet,self.request,self.manifest)

    def test_runtime_substitution_rejected(self):
        for field,value in [('executable_mappings',['/unknown']),('imported_files',{'/test/source':'changed'}),
            ('flags',{}),('prefix','/different'),('search_path',[])]:
            with self.subTest(field=field):
                packet=copy.deepcopy(self.packet);packet['runtime'][field]=value
                with self.assertRaises(ValueError):q.check(packet,self.request,self.manifest)

    def test_spawn_failure_retains_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            evidence=Path(d)/'case'
            with patch.object(q,'verify'),patch.object(q.subprocess,'Popen',side_effect=OSError('synthetic spawn failure')):
                with self.assertRaises(OSError):q.run(self.request,self.manifest,evidence)
            receipt=json.loads((evidence/'receipt.json').read_bytes())
            self.assertEqual(receipt['status'],'failed')
            self.assertIn('synthetic spawn failure',receipt['error'])
            self.assertIsNone(receipt['returncode'])

    def test_log_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);(directory/'airis logs').mkdir()
            (directory/'airis logs'/'data.log').write_text('synthetic')
            self.assertEqual(len(q.logs(directory)),1)
            (directory/'airis logs'/'link.log').symlink_to(directory/'airis logs'/'data.log')
            with self.assertRaises(ValueError):q.logs(directory)

if __name__=='__main__':unittest.main()
