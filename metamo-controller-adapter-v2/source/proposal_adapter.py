"""Read-only MetaMo proposal advice bound to the existing WorkingState contract.

Only the production controller may provide runner/current callbacks. A valid
receipt is auditable data, not cryptographic attestation or action permission.
No process, network, persistence, model or application action is implemented.
"""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from metamo_contract import (canonical, decode, keys, identifier, parse_request,
                             request_digest, validate_response, response_from_native)
from working_state import WorkingState

ROOT=str(Path(__file__).resolve().parents[2])
EXPECTED_MANIFEST='f848eb8166947cb01b8fa4d2ef47b5d3f2a2ae7f7d510b86a4fcb2271e65d05b'
UPSTREAM_COMMIT='bf97e50a68aa5059457092dfbe70699b7dd1dbe2'
IMPORTS=[ROOT+'/metamo-core-v4/source/numeric_compat.metta']+[ROOT+'/metamo-core-v4/upstream/'+name for name in (
    'core/state.metta','core/state_accessors.metta','openpsi/config.metta',
    'category/functors.metta','magus/decision.metta')]
SNAPSHOT_CAP=1024*1024
OFFERS_CAP=65536
RECEIPT_CAP=1024*1024
STATE_KEYS=('task_id','goal','phase','evidence','proposal','verification','executed_actions')
CHECKERS={'integer-arithmetic-v1':'verify_arithmetic','exact-quote-v1':'verify_quote','strict-invoice-v1':'verify_invoice'}

def require(condition,message):
    if not condition: raise ValueError(message)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def detached(value,cap): return decode(canonical(value),cap)

def restore_open(snapshot):
    snapshot=detached(snapshot,SNAPSHOT_CAP);keys(snapshot,STATE_KEYS)
    require(snapshot['phase']=='open' and type(snapshot['phase']) is str,'Open task required')
    require(snapshot['proposal'] is None and snapshot['verification'] is None,'Unproposed original state required')
    require(type(snapshot['executed_actions']) is int and snapshot['executed_actions']==0,'No action authority')
    require(type(snapshot['evidence']) is dict and 1<=len(snapshot['evidence'])<=16,'Evidence capacity')
    state=WorkingState(snapshot['task_id'],snapshot['goal'])
    for evidence_id,row in snapshot['evidence'].items():
        keys(row,('source','text','sha256'))
        require(type(row['text']) is str,'Evidence text type')
        require(type(row['sha256']) is str and row['sha256']==digest(row['text'].encode('utf-8')),'Evidence bytes/hash mismatch')
        state.add_evidence(evidence_id,row['source'],row['text'])
    require(canonical(state.snapshot())==canonical(snapshot),'Controller snapshot differs')
    return state

@dataclass(frozen=True)
class ProposalPlan:
    snapshot_json:bytes
    offers_json:bytes
    request_json:bytes
    revision:int

    def request(self): return parse_request(self.request_json)
    def snapshot(self): return decode(self.snapshot_json,SNAPSHOT_CAP)

def prepare(snapshot,revision,motivation,offers):
    """The controller supplies numerical features; this adapter does not infer them."""
    require(type(revision) is int and 1<=revision<=2**31-1,'Revision domain')
    state=restore_open(snapshot);snapshot=state.snapshot()
    offers=detached(offers,OFFERS_CAP)
    require(type(offers) is list and 1<=len(offers)<=8,'One to eight offers')
    ids=[];candidates=[]
    for index,offer in enumerate(offers):
        keys(offer,('proposal_id','proposal','correlations','risk','delta_goals'))
        ids.append(identifier(offer['proposal_id']))
        p=offer['proposal'];keys(p,('name','arguments','evidence_ids'))
        # Reuse exactly the existing finite inert proposal schema on a clone.
        scratch=restore_open(snapshot)
        scratch.propose(state.task_id,p['name'],p['arguments'],p['evidence_ids'])
        require(canonical(scratch.snapshot()['proposal'])==canonical(p),'Proposal altered on controller validation')
        candidates.append({'id':'p%02d'%index,'correlations':offer['correlations'],
                           'risk':offer['risk'],'delta_goals':offer['delta_goals']})
    require(len(set(ids))==len(ids),'Duplicate proposal ID')
    binding=canonical({'snapshot':snapshot,'revision':revision,'offers':offers,'motivation':motivation})
    request=parse_request(canonical({'version':1,'request_id':'metamo-'+digest(binding)[:48],
                                    'operation':'rank_proposals','state':motivation,'candidates':candidates}))
    return ProposalPlan(canonical(snapshot),canonical(offers),canonical(request),revision)

def validate_plan(plan):
    require(type(plan) is ProposalPlan,'Controller plan type')
    request=plan.request();offers=decode(plan.offers_json,OFFERS_CAP);snapshot=plan.snapshot()
    expected=prepare(snapshot,plan.revision,request['state'],offers)
    require(expected==plan,'Plan/request/proposal/evidence binding changed')
    return snapshot,offers,request

def assert_current(plan,current_snapshot,current_revision):
    validate_plan(plan)
    require(type(current_revision) is int and current_revision==plan.revision,'Stale revision')
    current=restore_open(current_snapshot).snapshot()
    require(canonical(current)==plan.snapshot_json,'Original task/evidence changed')

def validate_observation(plan,response,receipt):
    """Validate a controller-supplied native observation; never accepts score-only data."""
    snapshot,offers,request=validate_plan(plan)
    response=validate_response(canonical(response),request)
    receipt=detached(receipt,RECEIPT_CAP)
    require(type(receipt) is dict,'Receipt object required')
    for key,value in {'kind':'metamo','status':'passed','manifest_sha256':EXPECTED_MANIFEST,
                      'posthash_status':'completed-unchanged'}.items():
        require(receipt.get(key)==value,'Native receipt '+key)
    for key in ('native_tested','inputs_unchanged','group_empty'):
        require(receipt.get(key) is True,'Native completion flag '+key)
    require(receipt.get('authorizes_actions') is False,'Native authority escalation')
    require(type(receipt.get('executed_actions')) is int and receipt['executed_actions']==0,'Native action count')
    require(type(receipt.get('returncode')) is int and receipt['returncode']==0,'Native exit status')
    require(receipt.get('temporary_files')==[] and 'temporary_cleanup_error' not in receipt,'Temporary work not clean')
    require(receipt.get('finalization_errors',[])==[],'Native finalization incomplete')
    cleanup=receipt.get('cleanup');require(type(cleanup) is dict,'Cleanup record')
    require(cleanup.get('reaped') is True and cleanup.get('ownership')=='owned-through-final-signal','Owned cleanup incomplete')
    require(type(cleanup.get('returncode')) is int and cleanup['returncode']==0,'Cleanup exit status')
    require(type(receipt.get('seconds')) in (int,float) and math.isfinite(receipt['seconds']) and 0<=receipt['seconds']<=20,'Native duration cap')
    require(type(receipt.get('peak_rss_bytes')) is int and 0<receipt['peak_rss_bytes']<=256*1024**2,'Native RSS cap')
    require(type(receipt.get('minimum_available_bytes')) is int and receipt['minimum_available_bytes']>=4*1024**3,'Memory reserve')
    require(type(receipt.get('stdout')) is str and type(receipt.get('stderr')) is str,'Exact native streams')
    require(len(receipt['stdout'].encode())<=32768 and len(receipt['stderr'].encode())<=16384,'Native stream caps')
    require(receipt['stderr'].splitlines().count('ROKO_METAMO_OUTPUT_ROUTE_SENTINEL')==1 and 'ERROR:' not in receipt['stderr'] and '\u274c' not in receipt['stderr'],'Native diagnostics')
    packet=decode(receipt['stdout'].encode(),32768)
    keys(packet,('version','request','response','strict_imports','native_selection_symbol','native_scores','native_delta','helper_probes','runtime','executed_actions'))
    require(type(packet['version']) is int and packet['version']==1,'Packet version')
    require(type(packet['executed_actions']) is int and packet['executed_actions']==0,'Packet action count')
    require(canonical(packet['request'])==plan.request_json,'Native request differs from plan')
    require(canonical(packet['response'])==canonical(response),'Native response substitution')
    require(packet['strict_imports']==IMPORTS,'Source import identity/order changed')
    native=response_from_native(request,packet['native_scores'],packet['native_selection_symbol'],packet['native_delta'])
    require(canonical(native)==canonical(response),'Native selection or score substitution')
    require(canonical(packet['runtime'])==canonical(receipt.get('runtime')),'Runtime observation mismatch')
    keys(packet['runtime'],('python','executable_mappings'))
    require(canonical(packet['runtime']['python'])==b'[3,12,14]','Embedded runtime ABI')
    mappings=packet['runtime']['executable_mappings']
    require(type(mappings) is list and 3<=len(mappings)<=64 and all(type(p) is str for p in mappings),'Executable mapping bound')
    required={ROOT+'/recovery-second/runtime/swipl-basic/runtime/swipl/lib/swipl/bin/x86_64-linux/swipl',
              ROOT+'/recovery-second/runtime/swipl-basic/runtime/swipl/lib/swipl/lib/x86_64-linux/janus.so',
              ROOT+'/recovery-second/runtime/swipl-basic/runtime/recovered-python312/lib/libpython3.12.so.1.0'}
    require(required<=set(mappings) and len(set(mappings))==len(mappings),'Missing/duplicate executable maps')
    # Full ELF hashes and per-probe numeric validation remain the fixed gateway's
    # responsibility. This checks receipt linkage, not independent attestation.
    require(type(packet['helper_probes']) is list and len(packet['helper_probes'])==16,'Native compatibility probes incomplete')
    return response,receipt

def materialize_advice(plan,response,receipt,*,current_snapshot,current_revision):
    assert_current(plan,current_snapshot,current_revision)
    response,receipt=validate_observation(plan,response,receipt)
    snapshot,offers,request=validate_plan(plan)
    selected=[row['id'] for row in request['candidates']].index(response['selected_proposal_id'])
    offer=offers[selected];proposal=offer['proposal']
    evidence=[{'id':eid,**snapshot['evidence'][eid]} for eid in proposal['evidence_ids']]
    return {'schema':'roko-metamo-proposal-advice-v1','task_id':snapshot['task_id'],'revision':plan.revision,
            'snapshot_sha256':digest(plan.snapshot_json),'request_sha256':request_digest(request),
            'native_manifest_sha256':EXPECTED_MANIFEST,'upstream_commit':UPSTREAM_COMMIT,
            'native_receipt_sha256':digest(canonical(receipt)),'proposal_id':offer['proposal_id'],
            'proposal':proposal,'evidence':evidence,'scores':[{'proposal_id':o['proposal_id'],'score':s['score']} for o,s in zip(offers,response['scores'])],
            'proposed_delta_goals':response['proposed_delta_goals'],'runtime_integrity_status':'controller-receipt-validated-not-independent-attestation',
            'proposal_verification':'not-yet-checked','full_metamo_state_cycle':False,
            'original_state_changed':False,'persistent_state_changed':False,'task_closed':False,
            'authorizes_actions':False,'executed_actions':0}

def preview_check(plan,advice,checker):
    """Use existing deterministic checker on a detached clone, never save/close."""
    snapshot,offers,request=validate_plan(plan)
    require(type(checker) is str and checker in CHECKERS,'Explicit supported checker required')
    require(type(advice) is dict and advice.get('schema')=='roko-metamo-proposal-advice-v1','Advice schema')
    require(advice.get('authorizes_actions') is False and type(advice.get('executed_actions')) is int and advice['executed_actions']==0,'Advice has no action authority')
    require(advice.get('task_id')==snapshot['task_id'] and advice.get('revision')==plan.revision and advice.get('snapshot_sha256')==digest(plan.snapshot_json),'Advice identity')
    matches=[offer for offer in offers if offer['proposal_id']==advice.get('proposal_id')]
    require(len(matches)==1 and canonical(matches[0]['proposal'])==canonical(advice.get('proposal')),'Advice proposal identity')
    scratch=restore_open(snapshot);p=matches[0]['proposal']
    scratch.propose(scratch.task_id,p['name'],p['arguments'],p['evidence_ids'])
    checked=getattr(scratch,CHECKERS[checker])()
    return {'checker':checker,'verification':checked,'preview_snapshot':scratch.snapshot(),
            'original_snapshot_sha256':digest(plan.snapshot_json),'persistent_state_changed':False,
            'task_closed':False,'executed_actions':0,'authorizes_actions':False}

def score_and_offer(plan,*,run,current):
    """A trusted controller supplies its fixed gateway runner, never request data."""
    require(callable(run) and callable(current),'Controller callbacks required')
    snapshot,revision=current();assert_current(plan,snapshot,revision)
    response,receipt=run('metamo',plan.request())
    snapshot,revision=current();assert_current(plan,snapshot,revision)
    return materialize_advice(plan,response,receipt,current_snapshot=snapshot,current_revision=revision)
