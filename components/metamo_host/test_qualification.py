"""Acceptance rejects mismatched native evidence; no synthetic runtime claims."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('metamo_host_qualification',Path(__file__).with_name('qualify.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        _,self.request,self.winner=q.cases()[1]
        scores=[q.score(self.request['state'],c) for c in self.request['candidates']]
        symbol='metamo_candidate_1';delta=self.request['candidates'][1]['delta_goals']
        self.packet=dict(request=self.request,executed_actions=0,native_scores=scores,
            native_selection_symbol=symbol,native_delta=delta,
            response=q.response_from_native(self.request,scores,symbol,delta),
            strict_imports=[str(p) for p in q.IMPORTS],
            helper_probes=[dict(name=n,observed=v) for n,_,v in q.PROBES],
            runtime=dict(executable_mappings=['/synthetic/test-only']))
        self.manifest={'files':{'/synthetic/test-only':'unused'}}

    def test_consistent_packet(self):
        self.assertEqual(q.check(self.packet,self.request,self.winner,self.manifest)['selected_proposal_id'],self.winner)

    def test_corrupt_observations_rejected(self):
        for field,value in [('native_scores',[10,20]),('native_selection_symbol','metamo_candidate_0'),
            ('native_delta',[1]*8),('strict_imports',[]),('helper_probes',[]),
            ('executed_actions',1),('runtime',{'executable_mappings':['/unexpected']}),('response',{})]:
            with self.subTest(field=field):
                packet=copy.deepcopy(self.packet);packet[field]=value
                with self.assertRaises((ValueError,KeyError)):q.check(packet,self.request,self.winner,self.manifest)

    def test_source_and_membership_changes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source';p.write_text('original')
            m=dict(roots={d:False},trees={d:q.tree(d)},symlinks={},files={str(p):q.sha(p)})
            q.verify(m);p.write_text('changed')
            with self.assertRaises(ValueError):q.verify(m)
            p.write_text('original');(Path(d)/'addition').write_text('extra')
            with self.assertRaises(ValueError):q.verify(m)

if __name__=='__main__':unittest.main()
