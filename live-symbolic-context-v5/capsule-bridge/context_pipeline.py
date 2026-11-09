"""Generalized finite attention-to-literal-context assembly.

Controller-owned mandatory evidence and all provenance survive independently of
native focus. The injected runner is trusted controller code, never request data.
Only the outer actual process gate may claim native execution. No model, actions,
persistence, autonomous loop, expression parser or evaluator is present here.
"""
from ecan_guest_advisory import prepare_advice, select_context, assert_current
from ecan_guest_contract import canonical
from cognition_protocol import validate_response

def assemble(snapshot, revision, attention, required, *, capacity, count, max_bytes,
             run, current):
    plan=prepare_advice(snapshot,revision,attention,required,
                        focus_capacity=capacity,selection_count=count)
    def fresh():
        snap,rev=current()
        assert_current(plan,snap,rev)
        return snap,rev
    fresh()
    native,bank_receipt=run('ecan',plan.request())
    snap,rev=fresh()
    selected=select_context(plan,canonical(native),current_snapshot=snap,
        current_revision=rev,max_context_bytes=max_bytes)
    contexts=[]
    for evidence in selected['context']['evidence']:
        fresh()
        request={'version':1,'operation':'roundtrip','task_id':snapshot['task_id'],
                 'goal':snapshot['goal'],'revision':revision,'evidence':evidence}
        response,receipt=run('omega',request)
        validate_response(canonical(response),request)
        fresh()
        contexts.append({'request':request,'result':response,'receipt':receipt})
    # Construct the model-facing context only from independently checked literal
    # roundtrips, not from worker-supplied extra fields or mutation return terms.
    result={'version':1,'task_id':snapshot['task_id'],'goal':snapshot['goal'],
            'evidence':[x['result']['evidence'] for x in contexts]}
    if canonical(result)!=canonical(selected['context']):raise ValueError('Literal context differs from controller originals')
    return {'context':result,'selection':selected,'bank_response':native,
            'bank_receipt':bank_receipt,'omega':contexts,
            'authorizes_actions':False,'executed_actions':0,'persistent_state_changed':False}
