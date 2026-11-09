"""Framework-neutral desktop presentation; request proposals require user choice.

No transport, subprocess, automatic retry, recovery, or history mutation lives
here. Render all transcript strings as plain text, never markup. The server
remains responsible for verifying claim owner death on any recovery request.
"""
import json
import re
if __package__:
    from .client_diagnostics import describe_error,describe_transport_failure
else:
    from client_diagnostics import describe_error,describe_transport_failure

def _copy(value):
    return json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))
def _id(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',value) is not None

class DesktopDiagnostics:
    def __init__(self,original_request):
        request=_copy(original_request)
        if (type(request) is not dict or type(request.get('api_version')) is not int or request['api_version']!=2
                or request.get('op')!='turn' or not _id(request.get('session_id')) or not _id(request.get('request_id'))
                or type(request.get('expected_revision')) is not int or request['expected_revision']<0):
            raise ValueError('Expected original v2 turn identity')
        self._original=json.dumps(request,ensure_ascii=False,allow_nan=False)
        self._snapshot=None;self._guidance=None
    def transport_lost(self):self._guidance=describe_transport_failure()
    def receive_error(self,response):
        if type(response) is not dict:raise ValueError('Expected error packet')
        if response.get('session_id',self.original()['session_id'])!=self.original()['session_id']:
            raise ValueError('Error belongs to a different session')
        if response.get('request_id',self.original()['request_id'])!=self.original()['request_id']:
            raise ValueError('Error belongs to a different request')
        self._guidance=describe_error(response)
    def original(self):return json.loads(self._original)
    def receive_snapshot(self,packet):
        snap=_copy(packet);history=snap.get('history') if type(snap) is dict else None
        if (type(snap) is not dict or type(snap.get('api_version')) is not int or snap['api_version']!=2
                or snap.get('status')!='snapshot' or snap.get('session_id')!=self.original()['session_id']
                or type(snap.get('revision')) is not int or snap['revision']<0
                or type(history) is not list or len(history)>256 or len(history)%2
                or len(history)!=snap['revision']*2
                or (snap.get('pending') is not None and not _id(snap['pending']))):
            raise ValueError('Invalid matching complete snapshot')
        for i,message in enumerate(history):
            if (type(message) is not dict or set(message)!={'role','content'}
                    or message['role']!=('user' if i%2==0 else 'assistant')
                    or type(message['content']) is not str or not 0<len(message['content'])<=4000):
                raise ValueError('Invalid snapshot transcript')
        if self._snapshot is not None:
            prior=json.loads(self._snapshot)
            if snap['revision']<prior['revision'] or history[:len(prior['history'])]!=prior['history']:
                raise ValueError('Snapshot would regress or rewrite accepted history')
        self._snapshot=json.dumps(snap,ensure_ascii=False,allow_nan=False)
    def view(self):
        snap=json.loads(self._snapshot) if self._snapshot else None
        actions=['snapshot']
        if snap and self._guidance:
            if snap['pending'] is None and self._guidance['retry_mode'] in ('exact_original_request_after_snapshot','original_request_or_new_id_after_review'):
                actions.append('replay_original')
            if self._may_recover(snap):actions.append('recover_pending')
        return {'guidance':_copy(self._guidance),'transcript':snap['history'] if snap else [],
                'snapshot_revision':snap['revision'] if snap else None,
                'pending':snap['pending'] if snap else None,
                'render_as_plain_text':True,'automatic_requests':False,
                'available_actions':actions,
                'recovery_requires_verified_dead_owner':'recover_pending' in actions}
    def _may_recover(self,snap):
        original=self.original()
        return bool(self._guidance and
            (self._guidance['requires_verified_dead_owner'] or self._guidance['code']=='transport_failure')
            and snap['pending']==original['request_id']
            and snap['revision']==original['expected_revision'])
    def request_for_user_action(self,action,*,confirmed=False,owner_stopped=False):
        if confirmed is not True:raise ValueError('Explicit user confirmation required')
        original=self.original()
        if action=='snapshot':return {'api_version':2,'op':'snapshot','session_id':original['session_id']}
        if self._snapshot is None:raise ValueError('Inspect a matching snapshot first')
        snap=json.loads(self._snapshot)
        if action=='replay_original':
            if (self._guidance is None or self._guidance['retry_mode'] not in
                    ('exact_original_request_after_snapshot','original_request_or_new_id_after_review')
                    or snap['pending'] is not None):raise ValueError('Replay is not offered in this state')
            return original
        if action=='recover_pending':
            if owner_stopped is not True or not self._may_recover(snap):
                raise ValueError('Explicit stopped-owner confirmation and own matching claim required')
            return {'api_version':2,'op':'recover','session_id':original['session_id'],
                    'request_id':snap['pending'],'expected_revision':snap['revision']}
        raise ValueError('Unsupported desktop action')
