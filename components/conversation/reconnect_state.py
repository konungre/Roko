"""Local snapshot correlation; no networking, timers, retries or recovery execution."""
if __package__:
    from .desktop_draft import DesktopDraft
else:
    from desktop_draft import DesktopDraft

class ReconnectState:
    def __init__(self, draft):
        if not isinstance(draft,DesktopDraft): raise ValueError('Expected desktop draft controller')
        self._draft=draft;self._epoch=0;self._serial=0;self._ticket=None
    def service_lost(self):
        self._draft.transport_lost()
        self._epoch+=1;self._ticket=None
    def receive_error(self, packet):
        self._draft.receive_error(packet)
        self._epoch+=1;self._ticket=None
    def propose_action(self, action, *, confirmed=False, owner_stopped=False):
        if action=='snapshot': raise ValueError('Use correlated request_snapshot')
        if self._ticket is not None: raise ValueError('Snapshot review is still outstanding')
        return self._draft.propose(action,confirmed=confirmed,owner_stopped=owner_stopped)
    def review_and_release(self, *, confirmed=False):
        if self._ticket is not None: raise ValueError('Snapshot review is still outstanding')
        self._draft.review_and_release(confirmed=confirmed)
    def request_snapshot(self, *, confirmed=False):
        packet=self._draft.propose('snapshot',confirmed=confirmed)
        self._serial+=1;self._ticket=(self._epoch,self._serial)
        return dict(ticket=list(self._ticket),packet=packet)
    def receive_snapshot(self, ticket, packet):
        if (type(ticket) is not list or len(ticket)!=2
                or any(type(x) is not int for x in ticket)
                or self._ticket is None or tuple(ticket)!=self._ticket):
            raise ValueError('Snapshot reply is stale or uncorrelated')
        self._draft.receive_snapshot(packet)
        self._ticket=None
    def view(self):
        state=self._draft.view();active=state['active']
        if active is None:phase='idle'
        elif self._ticket is not None:phase='snapshot_requested'
        elif state['needs_snapshot']:phase='snapshot_required'
        elif active['pending'] is not None:phase='pending_owner_review'
        else:phase='snapshot_review_required'
        if active is not None and self._ticket is not None:
            active['available_actions']=['snapshot'];active['recovery_requires_verified_dead_owner']=False
        return dict(phase=phase,service_health='not_established',automatic_requests=False,
                    draft_state=state)
