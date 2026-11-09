"""Opt-in genuine native probe. No doubles, model inference or action dispatch."""
import argparse
import json
from pathlib import Path
import tempfile

from rebuilt_mork import RebuiltMORKCandidate
from durable_memory import DurableMemory
from conversation_store import ConversationStore


def probe(runtime):
    rows = []
    facts = [{'relation':'likes','args':['sam','tea']},
             {'relation':'likes','args':['jo','coffee']}]
    cases = [
        ('exact', facts, {'relation':'likes','args':['sam','tea']}),
        ('wildcards', facts, {'relation':'likes','args':[None,None]}),
        ('absent', facts, {'relation':'likes','args':['sam','coffee']}),
        ('empty', [], {'relation':'likes','args':[None,None]}),
        ('deduplicate', facts+facts, {'relation':'likes','args':[None,None]}),
        ('max_arity', [{'relation':'r','args':['a','b','c']}],
                      {'relation':'r','args':[None,'b',None]}),
        ('max_facts', [{'relation':'r','args':['a'+str(i)]} for i in range(16)],
                      {'relation':'r','args':[None]}),
    ]
    for name, source, query in cases:
        result = runtime.query_facts(source, query)
        # query_facts independently checks completeness and exact values.
        rows.append({'case':name, 'result':result})
    with tempfile.TemporaryDirectory(prefix='native-memory-probe-') as temp:
        path = Path(temp)/'evidence.sqlite'
        memory = DurableMemory(path, native_backend=runtime)
        record = memory.remember('s', facts[0], source='synthetic-probe', turn='t1')
        memory.close()
        memory = DurableMemory(path, native_backend=runtime)
        try:
            result = memory.recall('s', {'relation':'likes','args':['sam',None]})
            assert result['evidence'][0]['id'] == record
            rows.append({'case':'durable-reopen', 'result':result})
        finally: memory.close()
        path = Path(temp)/'conversation.sqlite'
        history = ConversationStore(path, native_backend=runtime)
        try:
            for i in range(20):
                history.append('s', admission_id='a'+str(i), role='user',
                    content='synthetic turn '+str(i), source='probe', expected_revision=i)
            receipt = history.prepare('s', request_id='q1', expected_revision=20)
            assert len(receipt['messages']) == 20 and len(receipt['evidence']) == 16
            history.accept_response('s', request_id='q1', request_token=receipt['request_token'],
                                    content='host-approved synthetic response')
            rows.append({'case':'conversation-native-index', 'result':receipt['memory'],
                         'authoritative_messages':20, 'indexed_messages':16})
        finally: history.close()
        history = ConversationStore(path, native_backend=runtime)
        try:
            assert history.snapshot('s')['revision'] == 21
            receipt = history.prepare('s', request_id='q2', expected_revision=21, role='assistant')
            assert len(receipt['evidence']) == 1
            rows.append({'case':'conversation-reopen', 'result':receipt['memory']})
        finally: history.close()
    return {'native_calls':len(rows), 'cases':rows, 'python_fallback':False,
            'petta_omega_loop_executed':False, 'external_actions_dispatched':0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    runtime = RebuiltMORKCandidate(args.manifest,
        expected_manifest_sha256=args.manifest_sha256)
    print(json.dumps(probe(runtime), indent=2))
