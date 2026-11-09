"""Versioned durable API; model output never selects storage paths or actions.

Claims precede ECAN/model execution. Commit precedes response delivery. A crash
between them can replay the stored response, never duplicate model inference.
Uncommitted claims require explicit recovery after the old worker has died.
"""
import json
import os

import conversation
from durable_store import Store, StoreError

store = None
current = None
immediate = None
completed = None


class DurableSession(conversation.Session):
    # Durable history is never silently windowed. Native 512-token admission may
    # reject earlier; the client can inspect history and explicitly start anew.
    max_history = 256
    max_output_tokens = 128

    def commit(self, omega_messages):
        global current, completed
        if current is None:
            raise ValueError('No durable claim')
        expected = self.history + [self.user_message(), {'role':'assistant','content':self.reply}]
        if self.reply is None or omega_messages != expected:
            raise ValueError('Incomplete Omega turn')
        if getattr(self.provider, 'profile', {}).get('mork_memory'):
            from mork_v2 import validate_history
            validate_history(expected)
        generation = self.provider.last_generation
        if generation is None:
            raise ValueError('Missing native generation receipt')
        response = {'api_version':2,'session_id':current['session_id'],
                    'request_id':current['request_id'],
                    'status':'truncated' if generation['finish_reason']=='length' else 'completed',
                    'text':self.reply,'context_ids':[f['id'] for f in self.context],
                    'executed_actions':0,'generation':generation,
                    'history_policy':'complete_no_omission'}
        if self.pending_component_results:
            response['cognitive_results']=self.pending_component_results
        saved = store.commit(current['token'],self.user_message(),expected[-1],response,
                             cognitive_history=self.cognitive_context)
        self.history = expected
        self.cognitive_history = [dict(item) for item in self.cognitive_context]
        self.pending_cognition = []
        self.pending_component_results = []
        self.pending = None
        current = None
        completed = json.dumps(saved,ensure_ascii=False)
        return completed


def initialize(provider, ranker, *, reasoner=None):
    global store
    store = Store(os.environ['ROKO_HISTORY_DB'])
    conversation.session = DurableSession(provider, ranker, reasoner=reasoner)
    if getattr(provider, 'profile', {}).get('mork_memory'):
        from mork_v2 import MAX_MESSAGES
        conversation.session.max_history = MAX_MESSAGES
    provider.allow_partial = True


def packet(value):
    def unique(pairs):
        result = {}
        for key,item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = item
        return result
    data = json.loads(value,object_pairs_hook=unique)
    if type(data) is not dict or type(data.get('api_version')) is not int or data['api_version'] != 2:
        raise ValueError('Expected API version 2')
    return data


def error_response(code, data):
    result = {'api_version':2,'status':'error','code':code,'executed_actions':0}
    for key in ('session_id','request_id'):
        value = data.get(key)
        if type(value) is str and len(value)<=128:
            result[key] = value
    return result


def prepare_line(line):
    global current, immediate, completed
    immediate = None
    completed = None
    data = {}
    try:
        if current is not None:
            raise RuntimeError('Previous native claim unresolved')
        data = packet(line)
        op = data.get('op')
        if op == 'limits':
            if set(data) != {'api_version','op','session_id'}:
                raise ValueError('Invalid limits fields')
            state = store.snapshot(data['session_id'])
            maximum = conversation.session.max_history
            used = len(state['history'])
            remaining = max(0,(maximum-used)//2)
            immediate = {'api_version':2,'status':'limits','session_id':data['session_id'],
                'revision':state['revision'],'executed_actions':0,
                'history_messages':used,'max_history_messages':maximum,
                'remaining_exchanges':remaining,'pending':state['pending'],
                'history_admits_turn':remaining>0 and state['pending'] is None,
                'input_token_limit':512,'max_output_tokens':128,
                'token_admission':'checked_during_native_inference',
                'history_policy':'complete_no_omission'}
            return False
        if op == 'snapshot':
            if set(data) != {'api_version','op','session_id'}:
                raise ValueError('Invalid snapshot fields')
            immediate = {'api_version':2,'status':'snapshot','session_id':data['session_id'],
                         'executed_actions':0,**store.snapshot(data['session_id'])}
            return False
        if op == 'recover':
            if set(data) != {'api_version','op','session_id','request_id','expected_revision'}:
                raise ValueError('Invalid recovery fields')
            immediate = {'api_version':2,'session_id':data['session_id'],
                         'request_id':data['request_id'],'executed_actions':0,
                         **store.recover(data['session_id'],data['request_id'],data['expected_revision'])}
            return False
        required = {'api_version','op','session_id','request_id','expected_revision','text','context'}
        if op != 'turn' or not required <= set(data) or set(data)-required-{'max_output_tokens','cognitive_tasks'}:
            raise ValueError('Invalid turn fields')
        maximum = data.get('max_output_tokens',128)
        if type(maximum) is not int or not 1<=maximum<=128:
            raise ValueError('Output budget must be 1..128')
        payload = {'text':data['text'],'context':data['context'],'max_output_tokens':maximum}
        tasks=[]
        if 'cognitive_tasks' in data:
            from learning import validate_tasks
            tasks=validate_tasks(data['cognitive_tasks'])
            payload['cognitive_tasks']=tasks
        claim = store.start(data['session_id'],data['request_id'],data['expected_revision'],payload)
        if claim['status'] == 'replayed':
            immediate = claim['response']
            return False
        current = {**claim,'session_id':data['session_id'],'request_id':data['request_id']}
        session = conversation.session
        session.history = claim['history']
        session.cognitive_history = claim['cognitive_history']
        session.cognitive_binding = {'session_id':data['session_id'],
            'request_id':data['request_id'],'revision':claim['revision']}
        session.max_output_tokens = maximum
        session.provider.max_tokens = maximum
        session.provider.last_error = None
        session.provider.last_generation = None
        if getattr(session.provider, 'profile', {}).get('mork_memory'):
            from mork_v2 import retrieve_history, history_digest, MAX_MESSAGES
            if len(claim['history']) >= MAX_MESSAGES:
                raise StoreError('history_limit','Native MORK conversation history capacity reached')
            text = conversation.bounded_text(data['text'])
            if len(text.encode('utf-8')) > 4096:
                raise ValueError('MORK message byte limit')
            try:
                session.history, receipt = retrieve_history(claim['history'],
                    {'session_id':data['session_id'],'request_id':data['request_id'],
                     'revision':claim['revision'],'history_sha256':history_digest(claim['history'])},
                     session.provider.profile)
            except Exception as error:
                raise conversation.NativePreparationError(str(error)) from error
            session.provider.mork_receipts.append(receipt)
        session.prepare({'text':data['text'],'context':data['context']},learning_tasks=tasks)
        return True
    except Exception as error:
        code = (error.code if isinstance(error,StoreError) else
                'native_turn_failed' if isinstance(error,conversation.NativePreparationError)
                else 'invalid_request')
        if current is not None:
            store.fail(current['token'],{'code':code})
            current = None
        immediate = error_response(code,data)
        return False


def immediate_json():
    return json.dumps(immediate,ensure_ascii=False)


def completed_json():
    if current is not None or completed is None:
        raise ValueError('Native step did not complete a durable commit')
    return completed


def abort():
    global current
    code = conversation.session.provider.last_error or 'native_turn_failed'
    data = current or {}
    if current is not None:
        store.fail(current['token'],{'code':code})
        current = None
    # A failed turn leaves the prior durable history authoritative.
    conversation.session.pending = None
    conversation.session.reply = None
    conversation.session.pending_cognition = []
    conversation.session.pending_component_results = []
    conversation.session.cognitive_context = [dict(item) for item in conversation.session.cognitive_history]
    return json.dumps(error_response(code,data),ensure_ascii=False)
