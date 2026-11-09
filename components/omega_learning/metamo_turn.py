"""Actual MetaMo scorer hook for an opaque immutable Omega conversation snapshot.

The caller owns the Omega turn and its full history. It supplies trusted native
runner/current callbacks and explicit numerical features. This hook never reads
messages as code, drops context, mutates a turn, verifies prose or grants tools.
"""
from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
if __package__:
    from .score_contract import canonical,decode,identifier,keys,parse_request,validate_response,response_from_native
else:
    from score_contract import canonical,decode,identifier,keys,parse_request,validate_response,response_from_native

MANIFEST='f848eb8166947cb01b8fa4d2ef47b5d3f2a2ae7f7d510b86a4fcb2271e65d05b'
UPSTREAM='bf97e50a68aa5059457092dfbe70699b7dd1dbe2'
SNAPSHOT_CAP=128*1024
TEXT_CAP=8192
OFFERS_CAP=96*1024

def require(ok,message):
    if not ok:raise ValueError(message)

def detached(value,cap):return decode(canonical(value),cap)
def digest(value):return sha256(value).hexdigest()

@dataclass(frozen=True)
class RuntimeBinding:
    """Trusted coordinator configuration, never a field supplied by a chat turn."""
    workspace: str
    def imports(self):
        base=Path(self.workspace)
        require(base.is_absolute() and str(base)==str(base.resolve()),'Canonical runtime workspace required')
        return [str(base/'metamo-core-v4/source/numeric_compat.metta')]+[
            str(base/'metamo-core-v4/upstream'/name) for name in
            ('core/state.metta','core/state_accessors.metta','openpsi/config.metta','category/functors.metta','magus/decision.metta')]
    def required_maps(self):
        base=Path(self.workspace)/'recovery-second/runtime/swipl-basic/runtime'
        return {str(base/'swipl/lib/swipl/bin/x86_64-linux/swipl'),str(base/'swipl/lib/swipl/lib/x86_64-linux/janus.so'),str(base/'recovered-python312/lib/libpython3.12.so.1.0')}

@dataclass(frozen=True)
class TurnPlan:
    turn_id: str
    revision: int
    snapshot_json: bytes
    offers_json: bytes
    request_json: bytes
    def snapshot(self):return decode(self.snapshot_json,SNAPSHOT_CAP)
    def request(self):return parse_request(self.request_json)


def prepare_turn(turn_id,snapshot,revision,motivation,offers):
    """Bind the complete caller-owned snapshot, never a filtered or truncated view."""
    turn_id=identifier(turn_id)
    require(type(revision) is int and 1<=revision<=2**31-1,'Revision domain')
    require(type(snapshot) is dict and bool(snapshot),'Nonempty conversation snapshot required')
    snapshot=detached(snapshot,SNAPSHOT_CAP)
    offers=detached(offers,OFFERS_CAP)
    require(type(offers) is list and 1<=len(offers)<=8,'One to eight response candidates')
    ids=[];candidates=[]
    for index,offer in enumerate(offers):
        keys(offer,('id','text','feature_provenance','correlations','risk','delta_goals'))
        ids.append(identifier(offer['id']))
        require(type(offer['text']) is str and 0<len(offer['text'].encode())<=TEXT_CAP,'Bounded nonempty response text')
        require(offer['feature_provenance'] in ('controller_policy','unverified_model_estimate','explicit_user') and type(offer['feature_provenance']) is str,'Explicit feature provenance required')
        candidates.append({'id':'p%02d'%index,'correlations':offer['correlations'],'risk':offer['risk'],'delta_goals':offer['delta_goals']})
    require(len(set(ids))==len(ids),'Duplicate response IDs')
    bound={'turn_id':turn_id,'revision':revision,'snapshot':snapshot,'offers':offers,'motivation':motivation}
    request=parse_request(canonical({'version':1,'request_id':'omega-turn-'+digest(canonical(bound))[:48],
        'operation':'rank_proposals','state':motivation,'candidates':candidates}))
    return TurnPlan(turn_id,revision,canonical(snapshot),canonical(offers),canonical(request))


def validate_plan(plan):
    require(type(plan) is TurnPlan,'Turn plan type')
    request=plan.request();offers=decode(plan.offers_json,OFFERS_CAP)
    expected=prepare_turn(plan.turn_id,plan.snapshot(),plan.revision,request['state'],offers)
    require(expected==plan,'Conversation/request/candidate binding changed')
    return request,offers


def assert_current(plan,current):
    validate_plan(plan)
    snapshot,revision=current()
    require(type(revision) is int and revision==plan.revision,'Stale turn revision')
    require(canonical(snapshot)==plan.snapshot_json,'Original conversation changed')


def validate_native(plan,response,receipt,binding):
    """Observe a trusted gateway result; this is not cryptographic attestation."""
    request,offers=validate_plan(plan)
    require(type(binding) is RuntimeBinding,'Trusted runtime binding required')
    response=validate_response(canonical(response),request)
    receipt=detached(receipt,1024*1024)
    require(type(receipt) is dict,'Native receipt object')
    for key,value in {'kind':'metamo','status':'passed','manifest_sha256':MANIFEST,'posthash_status':'completed-unchanged'}.items():
        require(receipt.get(key)==value,'Native receipt '+key)
    require(all(receipt.get(k) is True for k in ('native_tested','inputs_unchanged','group_empty')),'Native completion flags')
    require(receipt.get('authorizes_actions') is False and type(receipt.get('executed_actions')) is int and receipt['executed_actions']==0,'No native action authority')
    require(type(receipt.get('returncode')) is int and receipt['returncode']==0,'Native exit status')
    require(receipt.get('temporary_files')==[] and 'temporary_cleanup_error' not in receipt,'Temporary work incomplete')
    cleanup=receipt.get('cleanup',{})
    require(type(cleanup) is dict,'Cleanup object')
    require(cleanup.get('reaped') is True and cleanup.get('ownership')=='owned-through-final-signal' and type(cleanup.get('returncode')) is int and cleanup['returncode']==0,'Owned cleanup incomplete')
    require(type(receipt.get('seconds')) in (int,float) and math.isfinite(receipt['seconds']) and 0<=receipt['seconds']<=20,'Native duration')
    require(type(receipt.get('peak_rss_bytes')) is int and 0<receipt['peak_rss_bytes']<=256*1024**2,'Native memory cap')
    require(type(receipt.get('minimum_available_bytes')) is int and receipt['minimum_available_bytes']>=4*1024**3,'Host reserve')
    require(type(receipt.get('stdout')) is str and type(receipt.get('stderr')) is str,'Native stream types')
    require(len(receipt['stderr'].encode())<=16384 and receipt['stderr'].splitlines().count('ROKO_METAMO_OUTPUT_ROUTE_SENTINEL')==1 and 'ERROR:' not in receipt['stderr'] and '\u274c' not in receipt['stderr'],'Native diagnostic failure')
    packet=decode(receipt['stdout'].encode(),32768)
    keys(packet,('version','request','response','strict_imports','native_selection_symbol','native_scores','native_delta','helper_probes','runtime','executed_actions'))
    require(type(packet['version']) is int and packet['version']==1 and type(packet['executed_actions']) is int and packet['executed_actions']==0,'Native packet version/authority')
    require(canonical(packet['request'])==plan.request_json and canonical(packet['response'])==canonical(response),'Cross-turn/native response substitution')
    require(packet['strict_imports']==binding.imports(),'Native import identity/order')
    rebuilt=response_from_native(request,packet['native_scores'],packet['native_selection_symbol'],packet['native_delta'])
    require(canonical(rebuilt)==canonical(response),'Native selection substitution')
    require(packet['runtime']==receipt.get('runtime'),'Runtime record linkage')
    runtime=packet['runtime'];keys(runtime,('python','executable_mappings'))
    require(canonical(runtime['python'])==b'[3,12,14]','Native Python ABI')
    maps=runtime['executable_mappings']
    require(type(maps) is list and 3<=len(maps)<=64 and all(type(p) is str for p in maps) and len(set(maps))==len(maps) and binding.required_maps()<=set(maps),'Native executable map identity')
    require(type(packet['helper_probes']) is list and len(packet['helper_probes'])==16,'Missing native probes')
    # Full executable hashes and numeric probe acceptance remain the pinned
    # gateway's responsibility. There is no route from request data to a runner.
    return response,receipt,offers


def rank_turn(plan,*,run,current,binding):
    """One hook invocation within the real Omega turn, no model/task dispatch here."""
    require(callable(run) and callable(current),'Trusted controller callbacks required')
    assert_current(plan,current)
    response,receipt=run('metamo',plan.request())
    assert_current(plan,current)
    response,receipt,offers=validate_native(plan,response,receipt,binding)
    index=[x['id'] for x in plan.request()['candidates']].index(response['selected_proposal_id'])
    selected=offers[index]
    return {'schema':'roko.omega.metamo-turn-advice.v1','turn_id':plan.turn_id,'revision':plan.revision,
        'snapshot_sha256':digest(plan.snapshot_json),'request_sha256':digest(plan.request_json),
        'native_receipt_sha256':digest(canonical(receipt)),'native_manifest_sha256':MANIFEST,'upstream_commit':UPSTREAM,
        'selected_response_id':selected['id'],'response_text':selected['text'],
        'feature_provenance':selected['feature_provenance'],
        'scores':[{'id':offer['id'],'score':score['score']} for offer,score in zip(offers,response['scores'])],
        'proposed_delta_goals':response['proposed_delta_goals'],'content_verification':'not_established_by_ranking',
        'original_conversation_unchanged':True,'persistent_state_changed':False,
        'authorizes_actions':False,'executed_actions':0}


def prepare_conversation(snapshot,candidates,motivation):
    """Canonical live-system/omega-chat boundary; complete snapshot remains opaque data."""
    keys(snapshot,('version','session_id','revision','request_id','messages','user_text','evidence','components'))
    require(type(snapshot['version']) is int and snapshot['version']==1,'Conversation version')
    identifier(snapshot['session_id']);identifier(snapshot['request_id'])
    require(type(snapshot['messages']) is list and len(snapshot['messages'])<=64,'Message count')
    for message in snapshot['messages']:
        keys(message,('turn_id','role','content'));identifier(message['turn_id'])
        require(type(message['role']) is str and message['role'] in ('user','assistant','system','tool'),'Conversation role')
        require(type(message['content']) is str,'Message content type')
    require(type(snapshot['user_text']) is str and bool(snapshot['user_text']),'Current user text')
    require(type(snapshot['evidence']) is list and len(snapshot['evidence'])<=64,'Evidence count')
    eids=[]
    for evidence in snapshot['evidence']:
        keys(evidence,('id','text','provenance'));eids.append(identifier(evidence['id']))
        require(type(evidence['text']) is str,'Evidence text')
        require(type(evidence['provenance']) in (str,dict) and bool(evidence['provenance']),'Evidence provenance')
    require(len(set(eids))==len(eids),'Duplicate evidence IDs')
    require(type(snapshot['components']) is dict,'Component observation state')
    require(type(candidates) is list and 1<=len(candidates)<=8,'Conversation candidate count')
    offers=[]
    for candidate in candidates:
        keys(candidate,('id','text','features'));features=candidate['features']
        require(type(features) is dict and set(features) in ({'correlations','risk','delta_goals'},{'correlations','risk','delta_goals','provenance'}),'Candidate feature schema')
        # No provenance means no verified feature-origin claim. This label does
        # not upgrade caller-supplied estimates to observed or user-stated facts.
        offers.append({'id':candidate['id'],'text':candidate['text'],
            'feature_provenance':features.get('provenance','unverified_model_estimate'),
            'correlations':features['correlations'],'risk':features['risk'],'delta_goals':features['delta_goals']})
    return prepare_turn(snapshot['request_id'],snapshot,snapshot['revision'],motivation,offers)


def score_conversation(plan,*,run,current_snapshot_sha256,binding):
    """Live Omega hook. The controller computes the current full snapshot digest."""
    require(callable(current_snapshot_sha256),'Current full snapshot digest callback required')
    expected=digest(plan.snapshot_json)
    def current():
        observed=current_snapshot_sha256()
        require(type(observed) is str and observed==expected,'Conversation changed during selection')
        return plan.snapshot(),plan.revision
    advice=rank_turn(plan,run=run,current=current,binding=binding)
    score=next(x['score'] for x in advice['scores'] if x['id']==advice['selected_response_id'])
    return {'snapshot_sha256':expected,'candidate_id':advice['selected_response_id'],
        'selected_text':advice['response_text'],'score':score,'verification':'unverified',
        'executed_actions':0,'authorizes_actions':False,'original_conversation_unchanged':True,
        'persistent_state_changed':False,'provenance':{
            'component':'MetaMo','upstream_commit':UPSTREAM,'manifest_sha256':MANIFEST,
            'request_sha256':advice['request_sha256'],'native_receipt_sha256':advice['native_receipt_sha256'],
            'feature_provenance':advice['feature_provenance'],
            'scope':'actual gateway ranking observation; not factual verification or action permission'}}
