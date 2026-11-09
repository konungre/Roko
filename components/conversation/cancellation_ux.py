"""Explicit client proposals and correlated callbacks; never executes transport/actions."""
import copy,json,uuid
if __package__:
    from .desktop_draft import DesktopDraft
    from .reconnect_state import ReconnectState
    from .waiting_view import waiting_view
else:
    from desktop_draft import DesktopDraft
    from reconnect_state import ReconnectState
    from waiting_view import waiting_view

class CancellationUX:
    def __init__(self,text=''):
        self._draft=DesktopDraft(text);self._active=None;self._used=set();self._nonce=None
        self._worker=None;self._cancel=None;self._stopped=False;self._lost=False;self._reply=None;self._control=None;self._cancel_serial=0;self._last_recovery_error=None;self._replay_pending=False;self._last_turn_error=None;self._recovered=False
    def edit(self,text):self._draft.edit(text)
    def begin(self,request,*,confirmed=False,owned_worker=None):
        if owned_worker is not None and (type(owned_worker) is not str or not owned_worker or len(owned_worker)>128):
            raise ValueError('Expected locally owned opaque worker handle')
        if type(request) is not dict or any(type(request.get(k)) is not str for k in ('session_id','request_id')):
            raise ValueError('Expected request identity strings')
        key=(request['session_id'],request['request_id'])
        if key in self._used:raise ValueError('Prior identity requires explicit replay; new turns require a new ID')
        captured=self._draft.begin(request,confirmed=confirmed)
        self._used.add(key);self._active=captured;self._nonce=uuid.uuid4().hex;self._state=ReconnectState(self._draft)
        self._worker=owned_worker;self._cancel=None;self._stopped=False;self._lost=False;self._reply=None;self._control=None;self._last_recovery_error=None;self._replay_pending=False;self._last_turn_error=None;self._recovered=False
        return copy.deepcopy(captured)
    def worker_binding(self):
        if self._active is None or self._worker is None:return None
        return dict(turn=self._nonce,worker_handle=self._worker,session_id=self._active['session_id'],request_id=self._active['request_id'])
    def request_cancel(self,*,confirmed=False):
        self._require()
        if confirmed is not True or self._worker is None or self._stopped or self._reply is not None or self._cancel is not None:
            raise ValueError('Explicit cancellation of the current owned worker is unavailable')
        self._cancel_serial+=1
        self._cancel=dict(cancel_serial=self._cancel_serial,kind='stop_owned_worker',turn=self._nonce,worker_handle=self._worker,
                          session_id=self._active['session_id'],request_id=self._active['request_id'])
        return copy.deepcopy(self._cancel)
    def can_execute_cancel(self,proposal,*,current_binding):
        return bool(current_binding is not None and current_binding==self.worker_binding()
                    and self._active is not None and self._cancel is not None and proposal==self._cancel
                    and not self._stopped and self._reply is None)
    def cancel_not_executed(self,proposal):
        self._require()
        if self._cancel is None or proposal!=self._cancel or self._stopped:raise ValueError('Stale cancellation result')
        self._cancel=None;self._state.service_lost()
    def worker_stopped(self,proposal):
        self._require()
        if self._cancel is None or proposal!=self._cancel or self._stopped:raise ValueError('Stale or duplicate worker callback')
        self._stopped=True;self._lost=True;self._state.service_lost()
    def transport_lost(self):
        self._require();self._lost=True;self._replay_pending=False;self._state.service_lost()
    def inspect(self,*,confirmed=False):
        self._require();proposal=self._state.request_snapshot(confirmed=confirmed)
        return dict(ticket=dict(turn=self._nonce,snapshot=proposal['ticket']),packet=proposal['packet'])
    def receive_snapshot(self,ticket,packet):
        self._require()
        if type(ticket) is not dict or set(ticket)!={'turn','snapshot'} or ticket['turn']!=self._nonce:
            raise ValueError('Snapshot belongs to another captured turn')
        self._state.receive_snapshot(ticket['snapshot'],packet)
    def receive_error(self,packet):
        self._require()
        if (type(packet) is not dict or packet.get('session_id')!=self._active['session_id']
                or packet.get('request_id')!=self._active['request_id']):raise ValueError('Uncorrelated request error')
        self._state.receive_error(packet);self._replay_pending=False
        self._last_turn_error=self._draft.view()['active']['guidance']['code']
    def receive_reply(self,packet):
        self._require();original=self._active
        if self._recovered:raise ValueError('Conflicting terminal outcomes')
        if (type(packet) is not dict or type(packet.get('api_version')) is not int or packet['api_version']!=2
                or packet.get('session_id')!=original['session_id'] or packet.get('request_id')!=original['request_id']
                or type(packet.get('revision')) is not int or packet['revision']!=original['expected_revision']+1
                or packet.get('status') not in ('completed','truncated')
                or type(packet.get('text')) is not str or not packet['text'].strip() or len(packet['text'])>4000):
            raise ValueError('Uncorrelated committed reply')
        # A reply is displayed separately; only snapshots supply transcript history.
        clean=json.loads(json.dumps({key:packet[key] for key in ('api_version','session_id','request_id','revision','status','text')},ensure_ascii=False,allow_nan=False))
        if self._reply is not None and clean!=self._reply:raise ValueError('Reply changed for captured identity')
        self._draft.receive_reply(packet)
        if self._reply is None:self._state.service_lost()
        self._reply=clean;self._replay_pending=False;self._last_turn_error=None
    def replay(self,*,confirmed=False):
        self._require()
        if self._replay_pending or self._reply is not None or (self._cancel is not None and not self._stopped):raise ValueError('Review cancellation/result before replay')
        proposal=self._state.propose_action('replay_original',confirmed=confirmed)
        self._replay_pending=True;return proposal
    def recover(self,*,confirmed=False):
        self._require()
        if self._recovered or self._replay_pending or not self._stopped or self._reply is not None or self._control is not None:raise ValueError('Verified local stop and explicit inspection required')
        proposal=self._state.propose_action('recover_pending',confirmed=confirmed,owner_stopped=True)
        self._control=copy.deepcopy(proposal);return proposal
    def receive_recovery_reply(self,packet):
        self._require();control=self._control
        if (control is not None and type(packet) is dict and type(packet.get('api_version')) is int and packet['api_version']==2
                and packet.get('status')=='error' and packet.get('session_id')==control['session_id'] and packet.get('request_id')==control['request_id']):
            self._state.receive_error(packet);self._control=None
            self._last_recovery_error=self._draft.view()['active']['guidance']['code'];return
        if (control is None or type(packet) is not dict or type(packet.get('api_version')) is not int or packet['api_version']!=2
                or packet.get('status')!='interrupted' or packet.get('session_id')!=control['session_id']
                or packet.get('request_id')!=control['request_id'] or type(packet.get('revision')) is not int
                or packet['revision']!=control['expected_revision']):raise ValueError('Uncorrelated recovery reply')
        if self._reply is not None:raise ValueError('Conflicting terminal outcomes')
        self._control=None;self._last_recovery_error=None;self._recovered=True;self._state.service_lost()
    def review_and_release(self,*,confirmed=False):
        self._require()
        if self._replay_pending or self._control is not None or (self._cancel is not None and not self._stopped):raise ValueError('Control operation is unsettled')
        if self._reply is not None:
            current=self._draft.view()['active'];index=self._active['expected_revision']*2
            expected=[dict(role='user',content=self._active['text']),dict(role='assistant',content=self._reply['text'])]
            if current['transcript'][index:index+2]!=expected:raise ValueError('Inspect a snapshot containing the committed reply')
        self._state.review_and_release(confirmed=confirmed);self._active=None;self._worker=None
    def view(self,elapsed_seconds=0):
        if self._active is None:return dict(phase='idle',draft=self._draft.view()['draft'],automatic_requests=False)
        result=waiting_view(self._draft,elapsed_seconds,connection_lost=self._lost)
        phase='reply_received_review_required' if self._reply is not None else 'recovery_recorded_inspect_required' if self._recovered else 'worker_stopped_inspect_required' if self._stopped else 'stop_requested' if self._cancel is not None else 'error_review_required' if self._last_turn_error is not None else 'outcome_unknown' if self._lost else 'waiting'
        if self._reply is not None:
            result['message']='Committed reply received. Inspect and review the saved session.'
            result['request_outcome']='committed_reply_received'
        elif self._recovered:
            result['message']='Server recorded the request as interrupted. Inspect the saved session before sending a new turn.'
            result['request_outcome']='interrupted_reported'
        elif self._last_turn_error is not None:
            result['message']='Service status received. Inspect the session before deciding what to do.'
        result.update(reply_panel=self._draft.view()['active']['reply'],phase=phase,session_id=self._active['session_id'],request_id=self._active['request_id'],received_reply=copy.deepcopy(self._reply),worker_stopped=self._stopped,
                      cancel_available=self._worker is not None and self._cancel is None and not self._stopped and self._reply is None,
                      cancellation_means_recovery=False,last_recovery_error=self._last_recovery_error,last_turn_error=self._last_turn_error,replay_pending=self._replay_pending)
        return result
    def _require(self):
        if self._active is None:raise ValueError('No captured request')
