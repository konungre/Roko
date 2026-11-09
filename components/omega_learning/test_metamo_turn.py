"""Pure Omega turn-hook tests. Mock observations are not native evidence."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import ast
import unittest
from unittest.mock import patch
import metamo_turn as hook
from score_contract import canonical,response_from_native

BINDING=hook.RuntimeBinding('/synthetic-native-root')

def fixture():
    snapshot={'conversation_id':'session1','messages':[
        {'role':'user','text':'I am building Roko. Keep this context. 雪'},
        {'role':'assistant','text':'What part would you like to work on?'},
        {'role':'user','text':'Explain how my architecture fits together.'}],
        'evidence':{'source1':{'text':'Original evidence, preserved verbatim.'}},
        'omega_memory':{'task_state':'conversational'}}
    offers=[{'id':'response'+str(i),'text':text,'feature_provenance':'unverified_model_estimate',
        'correlations':[0]*8,'risk':.1,'delta_goals':[0]*8} for i,text in enumerate([
            'This candidate is deliberately higher ranked, but not independently verified.',
            'A different freeform answer, not an arithmetic/invoice fixture.'])]
    plan=hook.prepare_turn('turn1',snapshot,4,{'goals':[.5]*8,'modulators':[.5]*6},offers)
    return snapshot,offers,plan

def mock_observation(plan):
    req=plan.request();scores=[2.,1.];symbol='metamo_candidate_0';delta=req['candidates'][0]['delta_goals']
    response=response_from_native(req,scores,symbol,delta)
    runtime={'python':[3,12,14],'executable_mappings':sorted(BINDING.required_maps())}
    packet={'version':1,'request':req,'response':response,'strict_imports':BINDING.imports(),
        'native_selection_symbol':symbol,'native_scores':scores,'native_delta':delta,
        'helper_probes':[{'mock_only':True}]*16,'runtime':runtime,'executed_actions':0}
    receipt={'kind':'metamo','status':'passed','manifest_sha256':hook.MANIFEST,'posthash_status':'completed-unchanged',
        'native_tested':True,'inputs_unchanged':True,'group_empty':True,'authorizes_actions':False,'executed_actions':0,
        'returncode':0,'temporary_files':[],'cleanup':{'reaped':True,'ownership':'owned-through-final-signal','returncode':0},
        'seconds':1.,'peak_rss_bytes':65536,'minimum_available_bytes':8*1024**3,
        'stdout':canonical(packet).decode(),'stderr':'ROKO_METAMO_OUTPUT_ROUTE_SENTINEL\n','runtime':runtime}
    return response,receipt

class TurnTests(unittest.TestCase):
    def setUp(self):self.snapshot,self.offers,self.plan=fixture();self.response,self.receipt=mock_observation(self.plan)
    def rank(self,runner=None,current=None):
        return hook.rank_turn(self.plan,run=runner or (lambda *_:(self.response,self.receipt)),current=current or (lambda:(self.snapshot,4)),binding=BINDING)
    def test_freeform_text_selected(self):self.assertEqual(self.rank()['response_text'],self.offers[0]['text'])
    def test_all_history_retained(self):
        before=deepcopy(self.snapshot);self.rank();self.assertEqual(self.snapshot,before);self.assertEqual(self.plan.snapshot(),before)
    def test_ranking_not_verification(self):self.assertEqual(self.rank()['content_verification'],'not_established_by_ranking')
    def test_no_authority(self):self.assertFalse(self.rank()['authorizes_actions']);self.assertEqual(self.rank()['executed_actions'],0)
    def test_unverified_features_label(self):self.assertEqual(self.rank()['feature_provenance'],'unverified_model_estimate')
    def test_numeric_request_only(self):
        raw=self.plan.request_json.decode();self.assertNotIn('Original evidence',raw);self.assertNotIn('different freeform',raw);self.assertNotIn('messages',raw)
    def test_request_hash_binds_all_history(self):
        old=self.plan.request_json;self.snapshot['messages'][0]['text']='Changed fact';p=hook.prepare_turn('turn1',self.snapshot,4,{'goals':[.5]*8,'modulators':[.5]*6},self.offers);self.assertNotEqual(old,p.request_json)
    def test_no_truncation(self):
        self.offers[0]['text']='x'*8193
        with self.assertRaises(ValueError):hook.prepare_turn('turn1',self.snapshot,4,{'goals':[.5]*8,'modulators':[.5]*6},self.offers)
    def test_unknown_fields(self):
        self.offers[0]['command']='shell'
        with self.assertRaises(ValueError):hook.prepare_turn('turn1',self.snapshot,4,{'goals':[.5]*8,'modulators':[.5]*6},self.offers)
    def test_mandatory_feature_source(self):
        self.offers[0]['feature_provenance']='inferred_as_fact'
        with self.assertRaises(ValueError):hook.prepare_turn('turn1',self.snapshot,4,{'goals':[.5]*8,'modulators':[.5]*6},self.offers)
    def test_stale_before_native(self):
        with self.assertRaises(ValueError):self.rank(runner=lambda *_:self.fail('must not run'),current=lambda:(self.snapshot,5))
    def test_stale_after_native(self):
        def runner(*_):self.snapshot['messages'][0]['text']='concurrent update';return self.response,self.receipt
        with self.assertRaises(ValueError):self.rank(runner)
    def test_no_retry(self):
        calls=[]
        def runner(*_):calls.append(1);raise RuntimeError('actual failure')
        with self.assertRaises(RuntimeError):self.rank(runner)
        self.assertEqual(len(calls),1)
    def test_invalid_plan(self):
        self.plan=replace(self.plan,turn_id='another')
        with self.assertRaises(ValueError):self.rank()
    def test_wrong_manifest(self):
        self.receipt['manifest_sha256']='0'*64
        with self.assertRaises(ValueError):self.rank()
    def test_wrong_request(self):
        packet=hook.decode(self.receipt['stdout'].encode());packet['request']['request_id']='cross-turn';self.receipt['stdout']=canonical(packet).decode()
        with self.assertRaises(ValueError):self.rank()
    def test_unfinished_cleanup(self):
        self.receipt['cleanup']['reaped']=False
        with self.assertRaises(ValueError):self.rank()
    def test_missing_posthash(self):
        self.receipt['posthash_status']='not-completed'
        with self.assertRaises(ValueError):self.rank()
    def test_no_action_dispatch_or_persistence_import(self):
        tree=ast.parse(Path(hook.__file__).read_text());names={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertFalse(names&{'subprocess','socket','requests','os','state_store'})
    def test_no_native_claim_from_pure_tests(self):
        result=self.rank();self.assertNotIn('native_tested',result)
    def test_copied_score_contract(self):
        import hashlib,score_contract
        self.assertEqual(hashlib.sha256(Path(score_contract.__file__).read_bytes()).hexdigest(),'a0028e70899cfd792f8c1706613082573eb61469d2b0a1e91ea04db88ccae3f6')


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot={'version':1,'session_id':'chat1','revision':2,'request_id':'turn2',
            'messages':[{'turn_id':'turn1','role':'user','content':'Remember the basilisk design.'},
                        {'turn_id':'turn1','role':'assistant','content':'We can refine the chat bubble.'}],
            'user_text':'How should Omega coordinate this?',
            'evidence':[{'id':'e1','text':'Literal !(py-call NEVER) evidence. λ','provenance':{'source':'conversation'}}],
            'components':{'omega':{'observation':'pending'}}}
        self.candidates=[{'id':'c1','text':'A freeform candidate.','features':{'correlations':[0]*8,'risk':.1,'delta_goals':[0]*8}},
                         {'id':'c2','text':'Another candidate.','features':{'correlations':[0]*8,'risk':.1,'delta_goals':[0]*8}}]
        self.motivation={'goals':[.5]*8,'modulators':[.5]*6}
    def prepare(self):return hook.prepare_conversation(self.snapshot,self.candidates,self.motivation)
    def test_exact_omega_interface(self):
        plan=self.prepare();r,receipt=mock_observation(plan)
        advice=hook.score_conversation(plan,run=lambda *_:(r,receipt),current_snapshot_sha256=lambda:hook.digest(canonical(self.snapshot)),binding=BINDING)
        self.assertEqual(advice['candidate_id'],'c1');self.assertEqual(advice['selected_text'],self.candidates[0]['text']);self.assertEqual(advice['verification'],'unverified')
    def test_no_history_projection(self):self.assertEqual(self.prepare().snapshot(),self.snapshot)
    def test_revision_in_digest(self):
        before=self.prepare();self.snapshot['revision']=3;self.assertNotEqual(before.request_json,self.prepare().request_json)
    def test_components_in_digest(self):
        before=self.prepare();self.snapshot['components']['omega']['observation']='changed';self.assertNotEqual(before.request_json,self.prepare().request_json)
    def test_evidence_in_digest(self):
        before=self.prepare();self.snapshot['evidence'][0]['text']='changed';self.assertNotEqual(before.request_json,self.prepare().request_json)
    def test_current_text_in_digest(self):
        before=self.prepare();self.snapshot['user_text']='Different request';self.assertNotEqual(before.request_json,self.prepare().request_json)
    def test_hash_callback_stale(self):
        plan=self.prepare()
        with self.assertRaises(ValueError):hook.score_conversation(plan,run=lambda *_:self.fail('must not run'),current_snapshot_sha256=lambda:'0'*64,binding=BINDING)
    def test_hash_callback_changes_after_native(self):
        plan=self.prepare();r,receipt=mock_observation(plan);calls=[]
        def current():calls.append(1);return hook.digest(plan.snapshot_json) if len(calls)==1 else '0'*64
        with self.assertRaises(ValueError):hook.score_conversation(plan,run=lambda *_:(r,receipt),current_snapshot_sha256=current,binding=BINDING)
    def test_snapshot_extra_key(self):
        self.snapshot['command']='shell'
        with self.assertRaises(ValueError):self.prepare()
    def test_bad_version(self):
        self.snapshot['version']=True
        with self.assertRaises(ValueError):self.prepare()
    def test_message_shape(self):
        self.snapshot['messages'][0]['instruction']='run'
        with self.assertRaises(ValueError):self.prepare()
    def test_duplicate_evidence(self):
        self.snapshot['evidence'].append(deepcopy(self.snapshot['evidence'][0]))
        with self.assertRaises(ValueError):self.prepare()
    def test_no_feature_guessing(self):
        self.candidates[0]['features']={}
        with self.assertRaises(ValueError):self.prepare()
    def test_feature_source_explicit(self):
        self.candidates[0]['features']['provenance']='controller_policy'
        self.assertIn(b'controller_policy',self.prepare().offers_json)
    def test_large_context_fails_without_truncating(self):
        self.snapshot['messages'][0]['content']='x'*(128*1024)
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(len(self.snapshot['messages'][0]['content']),128*1024)


if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('Native execution forbidden')),patch('os.execve',side_effect=AssertionError('Native execution forbidden')):unittest.main()
