import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from fractions import Fraction
from contract import InvalidRequest, parse_request
from adapter import InvalidCoreResult, transition
from derive_slice import derive, SELECTION
from fixtures import base, rule, cases
from reference import ReferenceCore

ROOT=Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
    def bad(self, mutate):
        req=base();mutate(req)
        with self.assertRaises(InvalidRequest):parse_request(req)
    def test_valid(self):self.assertEqual(parse_request(base()).rules[0].core()[0][0],'right')
    def test_immutable(self):
        req=base();obj=parse_request(req);req['board'][0][0]='o';self.assertEqual(obj.board[0][0],'.')
    def test_digest_stable(self):self.assertEqual(parse_request(base()).digest(),parse_request(base()).digest())
    def test_digest_binds_evidence(self):
        req=base();old=parse_request(req).digest();req['updates']=[['r0',True]];self.assertNotEqual(old,parse_request(req).digest())
    def test_no_extra_keys(self):self.bad(lambda x:x.update(command='anything'))
    def test_no_missing_keys(self):self.bad(lambda x:x.pop('focus'))
    def test_no_booleans_as_time(self):self.bad(lambda x:x.update(now=True))
    def test_no_float_time(self):self.bad(lambda x:x.update(now=5.0))
    def test_time_bound(self):self.bad(lambda x:x.update(now=1001))
    def test_future_stamp(self):self.bad(lambda x:x['times'][0].__setitem__(0,6))
    def test_negative_stamp(self):self.bad(lambda x:x['times'][0].__setitem__(0,-1))
    def test_fixed_shape(self):self.bad(lambda x:x['board'].append(['.']*3))
    def test_ragged_board(self):self.bad(lambda x:x['board'][0].pop())
    def test_tokens_closed(self):self.bad(lambda x:x['board'][0].__setitem__(0,"__import__('os')"))
    def test_action_closed(self):self.bad(lambda x:x.update(action='run'))
    def test_callable_rejected(self):self.bad(lambda x:x.update(action=lambda:None))
    def test_focus_limit(self):self.bad(lambda x:x.update(focus=[['x',1]]*5))
    def test_duplicate_focus(self):self.bad(lambda x:x.update(focus=[['x',1],['x',2]]))
    def test_focus_nonfinite(self):self.bad(lambda x:x.update(focus=[['x',float('nan')]]))
    def test_focus_zero(self):self.bad(lambda x:x.update(focus=[['x',0]]))
    def test_rules_limit(self):self.bad(lambda x:x.update(rules=[rule(i) for i in range(9)]))
    def test_no_empty_conditions(self):self.bad(lambda x:x['rules'][0].update(conditions=[]))
    def test_condition_count(self):self.bad(lambda x:x['rules'][0].update(conditions=[[0,0,'x']]*5))
    def test_cardinal_only(self):self.bad(lambda x:x['rules'][0].update(conditions=[[1,1,'x']]))
    def test_offset_bound(self):self.bad(lambda x:x['rules'][0].update(conditions=[[0,3,'x']]))
    def test_duplicate_offsets(self):self.bad(lambda x:x['rules'][0].update(conditions=[[0,0,'x'],[0,0,'o']]))
    def test_duplicate_rule(self):self.bad(lambda x:x['rules'].append(rule(1)))
    def test_ids_ordered(self):self.bad(lambda x:x['rules'][0].update(id='r8'))
    def test_reward_range(self):self.bad(lambda x:x['rules'][0].update(values=[2,0]))
    def test_inventory_range(self):self.bad(lambda x:x.update(values=[0,5]))
    def test_no_zero_evidence(self):self.bad(lambda x:x['rules'][0].update(evidence=[0,0]))
    def test_evidence_ceiling(self):self.bad(lambda x:x['rules'][0].update(evidence=[20,2]))
    def test_evidence_booleans(self):self.bad(lambda x:x['rules'][0].update(evidence=[True,0]))
    def test_unknown_update(self):self.bad(lambda x:x.update(updates=[['r1',True]]))
    def test_boolean_update(self):self.bad(lambda x:x.update(updates=[['r0',1]]))
    def test_update_limit(self):self.bad(lambda x:x.update(updates=[['r0',True]]*9))
    def test_empty_rules_allowed(self):
        x=base();x['rules']=[];self.assertEqual(parse_request(x).rules,())
    def test_boundary_rules(self):
        x=base();x['rules']=[rule(i,action=('left','right','up','down')[i%4],result=('f','o')[i//4]) for i in range(8)]
        self.assertEqual(len(parse_request(x).rules),8)

class AdapterTests(unittest.TestCase):
    def run_case(self,name):
        req=next(x['request'] for x in cases() if x['id']==name)
        saved=copy.deepcopy(req);answer=transition(req,ReferenceCore());self.assertEqual(req,saved)
        self.assertFalse(answer['authority']);self.assertEqual(answer['external_actions'],0)
        self.assertNotIn('worker_kind',answer);return answer
    def test_no_native_import_in_tests(self):self.assertNotIn('nace_slice',sys.modules)
    def test_reward_sentinel(self):self.assertEqual(self.run_case('exact_reward')['prediction']['score_kind'],'certain_reward')
    def test_penalty_sentinel(self):self.assertEqual(self.run_case('exact_penalty')['prediction']['score_kind'],'certain_penalty')
    def test_partial(self):self.assertEqual(self.run_case('partial_match')['prediction']['match_score'],.5)
    def test_unattended(self):self.assertEqual(self.run_case('unattended_no_change')['prediction']['board'],base()['board'])
    def test_context(self):self.assertEqual(self.run_case('inventory_mismatch')['prediction']['board'],base()['board'])
    def test_action(self):self.assertEqual(self.run_case('action_mismatch')['prediction']['board'],base()['board'])
    def test_reversal(self):
        a=self.run_case('stronger_evidence');b=self.run_case('evidence_reversal')
        self.assertEqual(a['selected_rules'],['r0']);self.assertEqual(b['selected_rules'],['r1'])
        self.assertEqual(a['prediction']['board'][1][1],'f');self.assertEqual(b['prediction']['board'][1][1],'o')
    def test_saturation_actual_convention(self):self.assertEqual(self.run_case('saturated_evidence')['revised_truth'][0]['evidence'],[20,0])
    def test_evidence_tie_second(self):self.assertEqual(self.run_case('equal_truth_second_wins')['selected_rules'],['r1'])
    def test_longer_condition_tie(self):self.assertEqual(self.run_case('more_conditions_match_tie')['prediction']['board'][1][1],'k')
    def test_global_score(self):
        b=self.run_case('global_best_suppresses_partial')['prediction']['board'];self.assertEqual(b[0][0],'u');self.assertEqual(b[1][1],'x')
    def test_focus_age(self):self.assertEqual(self.run_case('inventory_mismatch')['prediction']['focus_age'],3)
    def test_json_has_no_infinities(self):
        for row in cases():json.dumps(transition(row['request'],ReferenceCore()),allow_nan=False)
    def test_truth_all_bounded_counts(self):
        for p in range(22):
            for n in range(22-p):
                if p+n==0:continue
                f,c=ReferenceCore.Hypothesis_TruthValue((p,n));e=ReferenceCore.Hypothesis_TruthExpectation((f,c))
                self.assertAlmostEqual(e,float(Fraction(2*p+1,2*(p+n+1))),places=14)
    def test_evidence_all_bounded_counts(self):
        for p in range(22):
            for n in range(22-p):
                if not p+n:continue
                for positive in (True,False):
                    out=ReferenceCore._AddEvidence({'r':(p,n)},'r',positive)['r']
                    self.assertTrue(1<=sum(out)<=21)
                    self.assertTrue(all(v>=0 for v in out))
    def test_input_mutation_rejected(self):
        class Mutator(ReferenceCore):
            @staticmethod
            def NACE_Predict(*args):
                args[2][0][0][0]='o';return ReferenceCore.NACE_Predict(*args)
        with self.assertRaises(InvalidCoreResult):transition(base(),Mutator())
    def test_invented_choice_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def Hypothesis_Choice(*args):return 'invented'
        with self.assertRaises(InvalidCoreResult):transition(cases()[6]['request'],Bad())
    def test_invalid_truth_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def Hypothesis_TruthValue(*args):return float('nan'),.5
        with self.assertRaises(InvalidCoreResult):transition(base(),Bad())
    def test_invalid_evidence_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def _AddEvidence(*args):return {}
        x=base();x['updates']=[['r0',True]]
        with self.assertRaises(InvalidCoreResult):transition(x,Bad())
    def test_invalid_score_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def NACE_Predict(*args):
                w,s,a,v=ReferenceCore.NACE_Predict(*args);return w,float('nan'),a,v
        with self.assertRaises(InvalidCoreResult):transition(base(),Bad())
    def test_false_sentinel_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def NACE_Predict(*args):
                w,s,a,v=ReferenceCore.NACE_Predict(*args);return w,float('inf'),a,v
        with self.assertRaises(InvalidCoreResult):transition(base(),Bad())
    def test_changed_time_rejected(self):
        class Bad(ReferenceCore):
            @staticmethod
            def NACE_Predict(*args):
                w,s,a,v=ReferenceCore.NACE_Predict(*args);w[2][0][0]=1;return w,s,a,v
        with self.assertRaises(InvalidCoreResult):transition(base(),Bad())

class SourceTests(unittest.TestCase):
    def test_exact_upstream_git_blobs(self):
        lock=json.loads((ROOT/'proof/upstream-lock.json').read_text())
        if any(not (ROOT / row['path']).is_file() for row in lock['files']):
            self.skipTest('Full exact-pin upstream review files are intentionally external')
        self.assertEqual(lock['commit'],'361fddf5f6885a60b6d5e0d179e0394da876df4c')
        for row in lock['files']:
            b=(ROOT/row['path']).read_bytes();self.assertEqual(len(b),row['bytes'])
            self.assertEqual(hashlib.sha256(b).hexdigest(),row['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),row['git_blob_sha'])
    def test_regeneration_byte_identity(self):
        if not (ROOT/'upstream/nace.py').is_file():
            self.skipTest('Full exact-pin upstream review files are intentionally external')
        data,records=derive();self.assertEqual(data,(ROOT/'source/nace_slice.py').read_text())
        self.assertEqual(records,json.loads((ROOT/'proof/slice-lineage.json').read_text())['functions'])
    def test_portable_slice_hash(self):
        lineage=json.loads((ROOT/'proof/slice-lineage.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'source/nace_slice.py').read_bytes()).hexdigest(),lineage['slice_sha256'])
    def test_portable_function_lineage(self):
        source=(ROOT/'source/nace_slice.py').read_text();lines=source.splitlines(keepends=True)
        nodes={n.name:n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        for row in json.loads((ROOT/'proof/slice-lineage.json').read_text())['functions']:
            n=nodes[row['function']];part=''.join(lines[n.lineno-1:n.end_lineno]).encode()
            self.assertEqual(hashlib.sha256(part).hexdigest(),row['sha256'])
    def test_only_seven_upstream_functions(self):
        tree=ast.parse((ROOT/'source/nace_slice.py').read_text())
        self.assertEqual({x.name for x in tree.body if isinstance(x,ast.FunctionDef)},set(sum(SELECTION.values(),())))
    def test_no_unsafe_imports_or_dynamic_calls_in_slice(self):
        tree=ast.parse((ROOT/'source/nace_slice.py').read_text())
        imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'copy')
        names={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(names & {'eval','exec','compile','input','open','__import__','print'})
    def test_no_top_level_calls_in_slice(self):
        tree=ast.parse((ROOT/'source/nace_slice.py').read_text())
        for node in tree.body:
            if not isinstance(node,ast.FunctionDef):self.assertFalse(any(isinstance(x,ast.Call) for x in ast.walk(node)))
    def test_license_preserved(self):
        text=(ROOT/'source/nace_slice.py').read_text();self.assertEqual(text.count('Copyright (c) 2024 Patrick Hammer, Peter Isaev'),2)
        self.assertIn('Permission is hereby granted',text)
    def test_worker_has_no_reference_fallback(self):
        tree=ast.parse((ROOT/'source/native_worker.py').read_text());names={n.name for node in ast.walk(tree) if isinstance(node,ast.Import) for n in node.names}
        self.assertIn('nace_slice',names);self.assertNotIn('reference',names)
    def test_authored_adapter_no_io_or_autonomy(self):
        tree=ast.parse((ROOT/'source/adapter.py').read_text());names={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(names & {'open','eval','exec','compile','input','__import__'})
    def test_custom_goal_always_none(self):
        tree=ast.parse((ROOT/'source/adapter.py').read_text());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='NACE_Predict']
        self.assertEqual(len(calls),1);self.assertIsNone(calls[0].args[-1].value)

if __name__=='__main__':unittest.main()
